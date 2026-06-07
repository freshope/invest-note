@AGENTS.md

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke gstack-office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke gstack-investigate
- Ship, deploy, push, create PR → invoke gstack-ship
- QA, test the site, find bugs → invoke gstack-qa
- Code review, check my diff → invoke gstack-review
- Update docs after shipping → invoke gstack-document-release
- Weekly retro → invoke gstack-retro
- Design system, brand → invoke gstack-design-consultation
- Visual audit, design polish → invoke gstack-design-review
- Architecture review → invoke gstack-plan-eng-review
- Save progress, checkpoint, resume → invoke gstack-checkpoint
- Code quality, health check → invoke gstack-health

## 하네스: invest-note 풀스택 작업

**목표:** BE(FastAPI)+FE(Next.js) 동반 변경이 필요한 feature 작업을 spec-planner / be-engineer / fe-engineer / integration-qa 4명 팀으로 분배하여 정합성·반복 함정·shape drift를 가드한다.

**트리거:** 풀스택 feature 구현·큰 리팩토링·BE+FE 동반 변경·재실행/부분 수정 요청 시 `invest-note-workflow` 스킬을 사용한다. 단일 영역 작은 변경, 단순 질문, 기존 커맨드(`/custom:spec-start`, `/custom:fix`, `/commit`) 단독 흐름에는 사용하지 않는다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-18 | 초기 구성 (4명 팀 + 워크플로 스킬) | 전체 | - |
| 2026-06-07 | spec-current/spec-history → issue-current/issue-history 경로 갱신 | 에이전트 4종 + 워크플로 스킬 | docs 폴더·파일 이름 변경 |
