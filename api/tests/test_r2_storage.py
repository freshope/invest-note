"""storage/r2.py 테스트 — presign URL 문자열 검증만(R2 네트워크 호출 절대 없음).

generate_presigned_url 은 로컬 SigV4 서명이라 네트워크 I/O 가 없다. 더미 자격증명으로
client 를 만들어 URL 에 bucket/key/만료/host/서명 파라미터가 실리는지 assert 한다.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from invest_note_api.config import Settings
from invest_note_api.errors import APIError
from invest_note_api.storage import r2



def _enabled_settings() -> Settings:
    return Settings(
        r2_endpoint_url="https://accountid.r2.cloudflarestorage.com",
        r2_bucket="statements",
        r2_access_key_id="dummy-access-key",
        r2_secret_access_key="dummy-secret-key",
    )


def _disabled_settings() -> Settings:
    return Settings()


def test_build_temp_key_prefix_and_ext():
    uid = uuid4()
    key = r2.build_temp_key(uid, "xlsx")
    assert key.startswith(f"temp/{uid}/")
    assert key.endswith(".xlsx")


def test_promote_key_temp_to_statement():
    """temp/{user}/{uuid}.{ext} → broker_statement/{동일 rest}. user/uuid/ext 보존."""
    uid = uuid4()
    temp = r2.build_temp_key(uid, "pdf")
    final = r2.promote_key(temp)
    assert final == f"broker_statement/{temp[len('temp/'):]}"
    assert final.startswith(f"broker_statement/{uid}/")
    assert final.endswith(".pdf")


def test_promote_key_rejects_non_temp():
    """temp prefix 아닌 key 는 400(방어)."""
    with pytest.raises(APIError) as exc:
        r2.promote_key("broker_statement/abc/x.xlsx")
    assert exc.value.status == 400


def test_copy_object_missing_source_400(monkeypatch):
    """소스 부재(업로드 미완료) → APIError(400). make_client 를 fake 로 대체해 네트워크 회피."""

    class _FakeClient:
        def copy_object(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "NoSuchKey"}}, "CopyObject"
            )

    monkeypatch.setattr(r2, "make_client", lambda settings: _FakeClient())
    with pytest.raises(APIError) as exc:
        r2.copy_object(_enabled_settings(), "temp/u/x.xlsx", "broker_statement/u/x.xlsx")
    assert exc.value.status == 400


def test_copy_object_success_calls_with_keys(monkeypatch):
    """정상 copy 는 bucket/src/dst 를 정확히 전달한다."""
    captured = {}

    class _FakeClient:
        def copy_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(r2, "make_client", lambda settings: _FakeClient())
    r2.copy_object(_enabled_settings(), "temp/u/x.xlsx", "broker_statement/u/x.xlsx")
    assert captured["Bucket"] == "statements"
    assert captured["Key"] == "broker_statement/u/x.xlsx"
    assert captured["CopySource"] == {"Bucket": "statements", "Key": "temp/u/x.xlsx"}


def test_delete_object_swallows_errors(monkeypatch):
    """delete_object 는 best-effort — 예외를 삼킨다(보상 삭제용)."""

    class _FakeClient:
        def delete_object(self, **kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")

    monkeypatch.setattr(r2, "make_client", lambda settings: _FakeClient())
    r2.delete_object(_enabled_settings(), "broker_statement/u/x.xlsx")  # 예외 없이 반환


def test_generate_put_url_contains_bucket_key_expiry_host():
    settings = _enabled_settings()
    key = "broker_statement/abc/file.xlsx"
    url = r2.generate_put_url(
        settings,
        key,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    # host = endpoint, path 에 bucket/key
    assert "r2.cloudflarestorage.com" in parsed.netloc
    assert "statements" in parsed.path
    assert "file.xlsx" in parsed.path
    # SigV4 서명 파라미터 + 만료
    assert qs["X-Amz-Expires"] == ["900"]
    assert "X-Amz-Signature" in qs
    assert "X-Amz-Credential" in qs


def test_generate_get_url_contains_attachment_disposition():
    settings = _enabled_settings()
    url = r2.generate_get_url(
        settings, "broker_statement/abc/file.xlsx", filename="원본.xlsx"
    )
    qs = parse_qs(urlparse(url).query)
    # ResponseContentDisposition 이 서명 쿼리에 실린다(키는 소문자 정규화될 수 있음)
    disp_key = next(k for k in qs if k.lower() == "response-content-disposition")
    assert "attachment" in qs[disp_key][0]


def test_generate_put_url_dormant_503():
    with pytest.raises(APIError) as exc:
        r2.generate_put_url(_disabled_settings(), "k", content_type="application/pdf")
    assert exc.value.status == 503


def test_make_client_dormant_503():
    with pytest.raises(APIError) as exc:
        r2.make_client(_disabled_settings())
    assert exc.value.status == 503
