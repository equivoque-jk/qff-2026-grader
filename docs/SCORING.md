# QFF 자동 채점 배점

기본 문항은 **100점**, 선택 심화는 **20점**으로 총점 상한은 **120점**입니다. 기본 점수와 추가 점수를 별도로 표시하며, 추가 점수를 100점에서 잘라내지 않습니다.

1번 측정·상태 준비는 30점, 2번 전송 복구·검증은 40점, 3번 고전 한계와 GHZ 협력 실험은 30점입니다. 선택 문항인 두 qubit의 전체 상태 전송은 추가 12점, 위상 오류 분석은 추가 8점입니다.

| 문항 | 내용 | 기본 | 추가 |
|---|---|---:|---:|
| 1-1 | 기준 상태 점검 — X와 Z 기댓값 | 3 | — |
| 1-2 | 기준 상태 점검 — H와 측정 통계 | 3 | — |
| 1-3 | 기준 상태 점검 — H 두 번 | 4 | — |
| 1-4 | 측정 basis로 상태 구별하기 | 5 | — |
| 1-5 | 전송 자원 준비 — 네 Bell 상태 | 7 | — |
| 1-6 | 공유 자원 검수 — 같은 기록을 남기는 두 장치 | 8 | — |
| 2-1 | 오류 재현과 진단 | 6 | — |
| 2-2 | 전송 회로 복구 | 18 | — |
| 2-3 | 전송 검증의 의미 | 7 | — |
| 2-4 | 교체 자원에 맞춰 장치 조정 | 9 | — |
| 3-1 | 고전 전략의 한계 | 7 | — |
| 3-2 | GHZ 측정 전략 | 10 | — |
| 3-3 | 승률과 Mermin 값 | 7 | — |
| 3-4 | 공유 자원 교체 | 6 | — |
| 2-5 | 선택 — 두 qubit의 상관관계까지 전송 | — | 12 |
| 3-5 | 선택 — 위상 오류와 고전 기준 | — | 8 |

## 제출과 부분 점수

- 참가자는 `TODO` 함수의 구현을 자유롭게 작성하고 안내한 형식의 회로 또는 계산 결과를 반환합니다. 퀴즈·참거짓·서술 답안 필드는 없습니다. 회로를 만들거나 수치를 계산하는 구현 방법 자체를 한 가지로 고정하지 않습니다. 1-1~1-3의 명시된 게이트 적용 조건은 검사합니다.
- 실험 메모와 출력은 풀이 과정 및 결과 해석을 확인하는 자료입니다. 자동 점수는 참가자 함수가 반환한 회로와 계산 결과에만 부여합니다. 서술 문장, 제공 코드의 단순 실행, 함수의 존재만으로는 점수를 주지 않습니다.
- 아래 세부 항목은 표시한 검사 조건을 **모두** 통과할 때 해당 점수를 얻습니다. Bell 목표, 초기 상태, 텔레포테이션 분기는 각각 독립된 항목으로 부분 점수를 받을 수 있습니다.
- `channel_complete`는 텔레포테이션 분기 점수의 필요조건이며 단독 배점이 없습니다. 모든 입력에서 해당 분기가 올바른 전송 채널인지 검사합니다.
- 미제출·형식 오류·오답·선행 회로 미완성으로 확인할 수 없는 항목은 0점입니다. 독립적으로 확인된 다른 항목의 점수는 유지합니다. 선행 회로 때문에 확인하지 못한 경우에는 `blocked` 표시와 피드백을 보존합니다.
- 상태 준비·상관관계·텔레포테이션 채널은 정확한 선형대수 계산으로 확인하며 전역 위상은 무시합니다. 수치 답안의 반환 형식과 허용오차는 [함수 반환 계약](RETURN_CONTRACTS.md)을 따릅니다.
- 기본 문항의 완료 여부와 추가 문항의 점수는 별개입니다. 추가 문항을 제출하지 않아도 기본 100점을 얻을 수 있습니다.

## 세부 배점

### 1-1 · 기준 상태 점검 — X와 Z 기댓값 — 3점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| X 한 번으로 \|1⟩ 준비 | 3 | `circuit.initial_zero_to_one`<br>`circuit.required_gates` |

### 1-2 · 기준 상태 점검 — H와 측정 통계 — 3점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| H 한 번으로 \|+⟩ 준비 | 3 | `circuit.initial_zero_to_plus`<br>`circuit.required_gates` |

### 1-3 · 기준 상태 점검 — H 두 번 — 4점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 초기 0에 H 두 번 적용 | 1 | `circuit.initial.0`<br>`circuit.required_gates.0` |
| 초기 1에 H 두 번 적용 | 1 | `circuit.initial.1`<br>`circuit.required_gates.1` |
| 초기 +에 H 두 번 적용 | 1 | `circuit.initial.+`<br>`circuit.required_gates.+` |
| 초기 -에 H 두 번 적용 | 1 | `circuit.initial.-`<br>`circuit.required_gates.-` |

### 1-4 · 측정 basis로 상태 구별하기 — 5점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 공통 국소 측정으로 +와 − 구별 | 5 | `circuit.discriminate_plus_minus` |

### 1-5 · 전송 자원 준비 — 네 Bell 상태 — 7점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| Phi+ 준비 | 1.75 | `circuit.target.Phi+` |
| Phi- 준비 | 1.75 | `circuit.target.Phi-` |
| Psi+ 준비 | 1.75 | `circuit.target.Psi+` |
| Psi- 준비 | 1.75 | `circuit.target.Psi-` |

### 1-6 · 공유 자원 검수 — 같은 기록을 남기는 두 장치 — 8점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| GHZ+ 준비 | 3 | `circuit.ghz` |
| 기록계를 버린 동전 혼합 상태 | 3 | `circuit.coin_reduced_state` |
| 공통 국소 측정의 판별 능력 | 2 | `circuit.local_basis_distinguishes` |

### 2-1 · 오류 재현과 진단 — 6점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 결함이 드러나는 입력 목록 | 2 | `output.failed_inputs` |
| 결함이 가려지는 입력 목록 | 2 | `output.masked_inputs` |
| + 입력에서 분기 00의 fidelity | 0.5 | `output.plus_branch.00` |
| + 입력에서 분기 01의 fidelity | 0.5 | `output.plus_branch.01` |
| + 입력에서 분기 10의 fidelity | 0.5 | `output.plus_branch.10` |
| + 입력에서 분기 11의 fidelity | 0.5 | `output.plus_branch.11` |

### 2-2 · 전송 회로 복구 — 18점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 지정된 Phi+ 공유 자원 | 2 | `circuit.shared_phi_plus` |
| 분기 00의 모든 입력 전송 | 4 | `circuit.channel_complete`<br>`circuit.branch.00` |
| 분기 01의 모든 입력 전송 | 4 | `circuit.channel_complete`<br>`circuit.branch.01` |
| 분기 10의 모든 입력 전송 | 4 | `circuit.channel_complete`<br>`circuit.branch.10` |
| 분기 11의 모든 입력 전송 | 4 | `circuit.channel_complete`<br>`circuit.branch.11` |

### 2-3 · 전송 검증의 의미 — 7점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 전송 검증의 평균 fidelity | 2 | `output.mean_fidelity` |
| 전송 검증의 최소 fidelity | 2 | `output.min_fidelity` |
| 고전 결과 수신 전 Bob의 평균 밀도행렬 | 3 | `output.bob_average_density` |

### 2-4 · 교체 자원에 맞춰 장치 조정 — 9점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| B=+에서 Bell pair를 만드는 회로 | 3 | `circuit.bell_from_b_plus` |
| Graph 자원의 분기 00 전송 | 1.5 | `circuit.channel_complete`<br>`circuit.branch.00` |
| Graph 자원의 분기 01 전송 | 1.5 | `circuit.channel_complete`<br>`circuit.branch.01` |
| Graph 자원의 분기 10 전송 | 1.5 | `circuit.channel_complete`<br>`circuit.branch.10` |
| Graph 자원의 분기 11 전송 | 1.5 | `circuit.channel_complete`<br>`circuit.branch.11` |

### 3-1 · 고전 전략의 한계 — 7점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 탐색의 최대 승률 | 2 | `search.maximum_rate` |
| 실제로 최적인 반환 전략 | 3 | `search.strategy_is_optimal` |
| 승률과 반환 전략의 일치 | 2 | `search.claim_matches_strategy` |

### 3-2 · GHZ 측정 전략 — 10점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| GHZ+ 게임 자원 | 2 | `circuit.ghz_resource` |
| 입력 000에서 목표 상관관계 | 2 | `circuit.game.E000` |
| 입력 011에서 목표 상관관계 | 2 | `circuit.game.E011` |
| 입력 101에서 목표 상관관계 | 2 | `circuit.game.E101` |
| 입력 110에서 목표 상관관계 | 2 | `circuit.game.E110` |

### 3-3 · 승률과 Mermin 값 — 7점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 입력 000의 correlator | 0.5 | `output.E.000` |
| 입력 011의 correlator | 0.5 | `output.E.011` |
| 입력 101의 correlator | 0.5 | `output.E.101` |
| 입력 110의 correlator | 0.5 | `output.E.110` |
| 입력 000의 승률 | 0.5 | `output.win.000` |
| 입력 011의 승률 | 0.5 | `output.win.011` |
| 입력 101의 승률 | 0.5 | `output.win.101` |
| 입력 110의 승률 | 0.5 | `output.win.110` |
| Mermin 값 | 1.5 | `output.M` |
| 평균 승률 | 1.5 | `output.p_win` |

### 3-4 · 공유 자원 교체 — 6점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 같은 X/Y 전략의 GHZ M | 1 | `output.ghz_M` |
| 같은 X/Y 전략의 GHZ 승률 | 1 | `output.ghz_p_win` |
| 같은 X/Y 전략의 동전 M | 1 | `output.coin_M` |
| 같은 X/Y 전략의 동전 승률 | 1 | `output.coin_p_win` |
| 일반 고전 출력의 최적 승률 | 2 | `output.classical_best` |

### 2-5 · 선택 — 두 qubit의 상관관계까지 전송 — 12점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| 고정 배치의 Bell pair 두 쌍 | 4 | `circuit.two_bell_pairs` |
| 분기 0000의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0000` |
| 분기 0001의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0001` |
| 분기 0010의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0010` |
| 분기 0011의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0011` |
| 분기 0100의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0100` |
| 분기 0101의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0101` |
| 분기 0110의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0110` |
| 분기 0111의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.0111` |
| 분기 1000의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1000` |
| 분기 1001의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1001` |
| 분기 1010의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1010` |
| 분기 1011의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1011` |
| 분기 1100의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1100` |
| 분기 1101의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1101` |
| 분기 1110의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1110` |
| 분기 1111의 전체 상태 전송 | 0.5 | `circuit.channel_complete`<br>`circuit.branch.1111` |

### 3-5 · 선택 — 위상 오류와 고전 기준 — 8점

| 항목 | 점수 | 필요한 검사 ID |
|---|---:|---|
| p=0의 M | 1 | `noise.0.M` |
| p=0의 승률 | 1 | `noise.0.p_win` |
| p=0.1의 M | 1 | `noise.0.1.M` |
| p=0.1의 승률 | 1 | `noise.0.1.p_win` |
| p=0.25의 M | 1 | `noise.0.25.M` |
| p=0.25의 승률 | 1 | `noise.0.25.p_win` |
| p=0.5의 M | 1 | `noise.0.5.M` |
| p=0.5의 승률 | 1 | `noise.0.5.p_win` |

배점의 기계 판독 원본은 `qff_grader/rubric.json`입니다. CLI 배점표와 JSON 결과는 같은 원본을 사용합니다. 기본 100점·추가 20점 합계와 검사 ID를 함께 검증합니다.
