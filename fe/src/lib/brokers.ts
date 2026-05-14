export type Broker = {
  name: string;
  color: string;
  slug: string;
};

export const BROKERS: Broker[] = [
  { name: "키움증권", color: "bg-orange-500", slug: "kiwoom" },
  { name: "미래에셋증권", color: "bg-blue-600", slug: "mirae-asset" },
  { name: "NH투자증권", color: "bg-green-600", slug: "nh" },
  { name: "삼성증권", color: "bg-blue-800", slug: "samsung" },
  { name: "KB증권", color: "bg-amber-500", slug: "kb" },
  { name: "한국투자증권", color: "bg-sky-600", slug: "korea-invest" },
  { name: "대신증권", color: "bg-red-600", slug: "daishin" },
  { name: "신한투자증권", color: "bg-indigo-500", slug: "shinhan" },
  { name: "메리츠증권", color: "bg-teal-600", slug: "meritz" },
  { name: "하나증권", color: "bg-emerald-500", slug: "hana" },
  { name: "토스증권", color: "bg-blue-500", slug: "toss" },
  { name: "부국증권", color: "bg-gray-600", slug: "buguk" },
  { name: "케이프투자증권", color: "bg-purple-600", slug: "cape" },
  { name: "다올투자증권", color: "bg-pink-600", slug: "daol" },
  { name: "DB금융투자", color: "bg-slate-600", slug: "dongbu" },
  { name: "이베스트투자증권", color: "bg-lime-600", slug: "ebest" },
  { name: "유진투자증권", color: "bg-yellow-600", slug: "eugene" },
  { name: "한화투자증권", color: "bg-orange-600", slug: "hanwha" },
  { name: "아이엠증권", color: "bg-cyan-600", slug: "im" },
  { name: "교보증권", color: "bg-red-700", slug: "kyobo" },
  { name: "신영증권", color: "bg-violet-600", slug: "shinyoung" },
  { name: "SK증권", color: "bg-rose-600", slug: "sk" },
  { name: "우리투자증권", color: "bg-blue-700", slug: "woori" },
  { name: "유안타증권", color: "bg-amber-600", slug: "yuanta" },
];

export function findBroker(name: string | null | undefined): Broker | undefined {
  if (!name || !name.trim()) return undefined;
  return BROKERS.find((b) => b.name === name);
}
