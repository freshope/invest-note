import { redirect } from "next/navigation";

// 바 /boards 진입은 첫 게시판(공지)으로.
export default function BoardsIndexPage() {
  redirect("/boards/notice");
}
