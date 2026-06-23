// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrokerStatementPanel } from "../BrokerStatementPanel";

const presign = vi.fn();
const submit = vi.fn();
const uploadToR2 = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    brokerStatementApi: {
      presign: (...a: unknown[]) => presign(...a),
      submit: (...a: unknown[]) => submit(...a),
      uploadToR2: (...a: unknown[]) => uploadToR2(...a),
    },
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/analytics", () => ({ capture: vi.fn() }));

function makeFile(name = "내역.xlsx", type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") {
  return new File(["x"], name, { type });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BrokerStatementPanel", () => {
  it("동의 미체크·파일 미선택 시 제보 버튼이 비활성화된다", () => {
    render(
      <BrokerStatementPanel
        open
        onOpenChange={vi.fn()}
        defaultType="unsupported_broker"
        brokerSource={{ mode: "fixed", label: "키움증권" }}
      />,
    );
    expect((screen.getByRole("button", { name: "제보하기" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("증권사(fixed)+파일+동의가 모두 충족되면 제보 버튼이 활성화되고, presign→upload→submit 순서로 호출한다", async () => {
    presign.mockResolvedValue({
      upload_url: "https://r2.example/statements/key?sig",
      storage_key: "broker_statement/u/abc.xlsx",
      bucket: "statements",
      expires_in: 900,
    });
    uploadToR2.mockResolvedValue(undefined);
    submit.mockResolvedValue({ post_id: "p1", attachment: {} });
    const onOpenChange = vi.fn();

    render(
      <BrokerStatementPanel
        open
        onOpenChange={onOpenChange}
        defaultType="unsupported_broker"
        brokerSource={{ mode: "fixed", label: "키움증권" }}
      />,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = makeFile();
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByLabelText("개인정보 수집·이용 동의"));

    const btn = screen.getByRole("button", { name: "제보하기" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);

    fireEvent.click(btn);

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));

    // content_type 단일 소스 — presign·submit 에 동일 content_type, submit consent=true.
    const presignArg = presign.mock.calls[0][0];
    expect(presignArg.content_type).toBe(file.type);
    expect(uploadToR2).toHaveBeenCalledWith(
      "https://r2.example/statements/key?sig",
      file,
      file.type,
    );
    const submitArg = submit.mock.calls[0][0];
    expect(submitArg.type).toBe("unsupported_broker");
    expect(submitArg.broker).toBe("키움증권");
    expect(submitArg.consent).toBe(true);
    expect(submitArg.attachment.storage_key).toBe("broker_statement/u/abc.xlsx");
    expect(submitArg.attachment.content_type).toBe(file.type);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("uploadToR2 (raw PUT)", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
  });
  afterEach(() => {
    global.fetch = realFetch;
  });

  it("PUT + Content-Type 만 보내고 Authorization 헤더는 없다", async () => {
    const { brokerStatementApi } = await vi.importActual<typeof import("@/lib/api-client")>(
      "@/lib/api-client",
    );
    const file = makeFile();
    await brokerStatementApi.uploadToR2("https://r2.example/key?sig", file, file.type);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://r2.example/key?sig");
    expect(init.method).toBe("PUT");
    expect(init.headers).toEqual({ "Content-Type": file.type });
    expect(init.headers).not.toHaveProperty("Authorization");
    expect(init.body).toBe(file);
  });
});
