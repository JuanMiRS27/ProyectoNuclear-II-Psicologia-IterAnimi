// Claves de TanStack Query por dominio. Un solo lugar para que las invalidaciones sean precisas.
// La caché completa solo se vacía al cambiar de identidad (ver providers/SessionProvider).

export const queryKeys = {
  me: () => ['me'] as const,
  users: {
    all: () => ['users'] as const,
    list: (filters: unknown) => ['users', 'list', filters] as const,
  },
  spaces: {
    all: () => ['spaces'] as const,
    list: (filters: unknown) => ['spaces', 'list', filters] as const,
    detail: (id: string) => ['spaces', id] as const,
    report: (id: string) => ['spaces', id, 'report'] as const,
  },
  cases: {
    all: () => ['cases'] as const,
    list: (filters: unknown) => ['cases', 'list', filters] as const,
    detail: (id: string) => ['cases', id] as const,
  },
  sessions: {
    all: () => ['sessions'] as const,
    list: () => ['sessions', 'list'] as const,
    mine: () => ['sessions', 'mine'] as const,
    detail: (id: string) => ['sessions', id] as const,
    convocations: (id: string) => ['sessions', id, 'convocations'] as const,
    code: (id: string, cid: string) => ['sessions', id, 'convocations', cid, 'code'] as const,
    summary: (id: string) => ['sessions', id, 'reports', 'summary'] as const,
    students: (id: string) => ['sessions', id, 'reports', 'students'] as const,
    grades: (id: string) => ['sessions', id, 'reports', 'grades'] as const,
    criteria: (id: string) => ['sessions', id, 'reports', 'criteria'] as const,
    questions: (id: string) => ['sessions', id, 'reports', 'questions'] as const,
    evaluations: (id: string) => ['sessions', id, 'evaluations'] as const,
  },
  evaluations: {
    detail: (participationId: string) => ['evaluations', participationId] as const,
  },
  student: {
    all: () => ['student'] as const,
    session: (id: string) => ['student', 'session', id] as const,
    attempts: () => ['student', 'attempts'] as const,
    attempt: (id: string) => ['student', 'attempt', id] as const,
    questionnaire: (id: string) => ['student', 'questionnaire', id] as const,
    results: () => ['student', 'results'] as const,
    result: (id: string) => ['student', 'results', id] as const,
  },
  notifications: {
    all: () => ['notifications'] as const,
    list: () => ['notifications', 'list'] as const,
    unread: () => ['notifications', 'unread'] as const,
  },
  deliveries: {
    all: () => ['deliveries'] as const,
    list: (filters: unknown) => ['deliveries', 'list', filters] as const,
  },
} as const
