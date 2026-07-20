"""_looks_encrypted magic 판별 단위테스트 — 암호화 파일에 비밀번호 안내를 띄우기 위한 게이트.

레거시 .xls(BIFF)가 OLE magic 을 공유하므로 'EncryptedPackage' 스트림명까지 봐야
false positive 를 막는다는 점을 회귀로 고정한다.
"""
from invest_note_api.services.broker_capture import _looks_encrypted

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ENC_STREAM = "EncryptedPackage".encode("utf-16-le")


def test_encrypted_xlsx_ole_with_stream_is_detected():
    blob = _OLE_MAGIC + b"\x00" * 32 + _ENC_STREAM + b"\x00" * 16
    assert _looks_encrypted(blob) is True


def test_legacy_xls_ole_without_stream_is_not_flagged():
    # 레거시 BIFF .xls 도 OLE magic 을 갖지만 EncryptedPackage 스트림은 없다 → 암호화 아님.
    blob = _OLE_MAGIC + b"\x09\x08" + b"legacy biff content" * 8
    assert _looks_encrypted(blob) is False


def test_normal_xlsx_zip_is_not_flagged():
    # 일반 xlsx 는 ZIP('PK') 컨테이너.
    assert _looks_encrypted(b"PK\x03\x04" + b"\x00" * 64) is False


def test_encrypted_pdf_with_encrypt_dict_is_detected():
    blob = b"%PDF-1.6\n" + b"...trailer... /Encrypt 12 0 R ..." + b"\n%%EOF"
    assert _looks_encrypted(blob) is True


def test_plain_pdf_without_encrypt_is_not_flagged():
    blob = b"%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\n%%EOF"
    assert _looks_encrypted(blob) is False


def test_unknown_bytes_are_not_flagged():
    assert _looks_encrypted(b"random garbage not a document") is False
