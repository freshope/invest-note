"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

/**
 * 사용자 정의 태그 레지스트리(가나다순) 조회.
 * 폼 그리드에서 프리셋과 함께 선택용 칩으로 노출한다.
 * 추가/삭제는 useCreate/DeleteCustomTag 가 invalidate 로 즉시 반영하므로, 변경 없는 동안의
 * 폼 재진입·앱 resume(focus) 마다의 중복 refetch 를 막도록 staleTime 을 둔다.
 */
export function useCustomTags() {
  const { data } = useQuery({
    queryKey: queryKeys.customTags,
    queryFn: () => tradesApi.customTags(),
    staleTime: 5 * 60 * 1000,
  });
  return data ?? [];
}

/**
 * 레지스트리에 태그 추가(멱등). 성공 시 레지스트리 invalidate.
 * 거래는 변경하지 않으므로 trades 는 invalidate 하지 않는다(라벨은 폼 제출 시 trade 에 저장됨).
 */
export function useCreateCustomTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (label: string) => tradesApi.createCustomTag(label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.customTags });
    },
  });
}

/**
 * 레지스트리에서 태그 삭제. 성공 시 레지스트리 invalidate.
 * 과거 거래의 라벨은 BE 가 유지하므로 trades 는 invalidate 하지 않는다.
 */
export function useDeleteCustomTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tradesApi.deleteCustomTag(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.customTags });
    },
  });
}
