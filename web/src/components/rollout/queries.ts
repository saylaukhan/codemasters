import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { assignAgentUpdate, getRolloutSchools, getRolloutSummary, type RolloutFilter } from '../../api/rollout'

/** How many schools a list shows; the rest is counted by «Ещё N школ» (docs/design/README.md §6.4). */
export const ROLLOUT_LIMIT = 20

export const useRolloutSummary = () =>
  useQuery({
    queryKey: ['rollout', 'summary'],
    queryFn: ({ signal }) => getRolloutSummary({}, signal),
    placeholderData: keepPreviousData,
  })

export const useRolloutSchools = (filter: RolloutFilter) =>
  useQuery({
    queryKey: ['rollout', 'schools', filter],
    queryFn: ({ signal }) => getRolloutSchools({ filter, limit: ROLLOUT_LIMIT }, signal),
    placeholderData: keepPreviousData,
  })

/** «Назначить обновление»: the lists and the counters of the computers change with it (T-50). */
export const useAssignAgentUpdate = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: assignAgentUpdate,
    onSuccess: () =>
      Promise.all(
        [['rollout'], ['devices'], ['admin']].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      ),
  })
}
