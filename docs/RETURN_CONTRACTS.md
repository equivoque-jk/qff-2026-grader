# 함수 반환 계약 — qff_local_2026_v1

문제지에 제공된 23개 함수의 `TODO BEGIN`과 `TODO END` 사이를 구현하세요. 함수 선언, 초기화 코드와 마지막 `return`은 유지하고, 아래 형식의 회로 또는 수치를 반환하도록 작성합니다. 계산 과정과 결과 해석은 실험 메모에 적습니다. 실험 메모와 서술 답안은 자동 점수에 포함되지 않습니다.

| 문항 | 함수 | 반환값과 순서 |
|---|---|---|
| 1-1 | `build_circuit_1_1()` | X 한 번을 적용하는 측정 없는 `QuantumCircuit(1)` |
| 1-2 | `build_circuit_1_2()` | H 한 번을 적용하는 측정 없는 `QuantumCircuit(1)` |
| 1-3 | `build_circuit_1_3(initial_state)` | 입력 `"0","1","+","-"`의 제공 준비 뒤 HH를 추가한 회로 |
| 1-4 | `discrimination_basis()` | 후보 정보 없이 공통으로 쓰는 국소 1-qubit 측정 basis |
| 1-5 | `bell_transform(target)` | 고정 입력 `\|q1 q0>=\|01>` 뒤에 붙이는 2-qubit 회로 |
| 1-6 | `build_ghz_state()`, `build_coin_flip_state()`, `correlation_basis()` | 각각 3-qubit GHZ, 4-qubit coin 정화, 3-qubit 국소 basis |
| 2-1 | `teleportation_diagnosis()` | `(failed_inputs, masked_inputs, plus_branch_fidelities)` |
| 2-2 | `shared_pair()`, `alice_encoder()`, `bob_decoder()` | 각각 `QC(2)`, `QC(2)`, `QC(1,2)` |
| 2-3 | `teleportation_validation()` | `(mean_fidelity, min_fidelity, bob_average_density)` |
| 2-4(a) | `bell_pair_from_b_plus()` | 초기 A=0, B=+ 뒤에 붙여 Phi+를 만드는 `QC(2)` |
| 2-4(b) | `bob_graph_decoder()` | 고정 graph 자원과 자신의 2-2 Alice에 맞는 `QC(1,2)` |
| 3-1 | `classical_search()` | `(best_probability, (sa,sb,sc))`, 각 전략은 `(출력0,출력1)` |
| 3-2 | `build_ghz3()`, `local_basis(party,input_bit)` | 3-qubit 자원, 각자 자신의 입력에 대한 `QC(1)` |
| 3-3 | `mermin_report()` | `(correlators, win_rates, M, p_win)` |
| 3-4 | `resource_comparison()` | `(ghz_M, ghz_p_win, coin_M, coin_p_win, classical_best)` |
| 선택 2-5 | `shared_pairs_2q()`, `bob_decoder_2q()` | 각각 `QC(4)`, `QC(2,4)` |
| 선택 3-5 | `phase_noise_metrics()` | `(result_p0,result_p01,result_p025,result_p05)`, 각각 `(M,p_win)` |

- 2-1의 failed/masked 입력은 `"0","1","+","-","+i","-i"` 중 해당하는 **모든** 문자열을 중복 없이 반환합니다. 집합 의미의 순서는 무관하지만 반환 타입은 tuple/list입니다. 분기 fidelity는 `|+>` 입력에서 정규화한 조건부 fidelity이며 `(00,01,10,11)` 즉 `c1 c0` 순서입니다. 제공된 결함 회로를 진단합니다.
- 2-3은 완성한 2-2에서 기준 상태 6개와 Haar 상태 20개의 평균·최소 fidelity를 반환합니다. `bob_average_density`는 기준 입력 `0`에서 고전 결과를 아직 받기 전, 보정을 적용하기 전 Bob의 결과 평균 상태입니다. `2×2` NumPy 복소 배열, 숫자 중첩 list 또는 Qiskit `DensityMatrix`를 사용할 수 있습니다. 심판의 입력 준비 정보를 Bob의 decoder에 전달하지 않습니다.
- 2-4(a)의 입력 준비 `B=+`는 채점기가 적용합니다. 함수는 그 뒤에 붙일 변환만 반환합니다. 추가 qubit·측정·reset 없이 H/X/Z/CX를 사용할 수 있습니다.
- 3-3의 `correlators`와 `win_rates`는 각각 길이 4이며 `(000,011,101,110)` 순서입니다. `p_win`은 네 입력의 균등 평균 승률입니다.
- 3-4는 3-2에서 한 번 고정한 여섯 측정 basis를 GHZ와 coin 양쪽에 사용합니다. `classical_best`는 고전 최적 전략의 승률입니다. coin에 적용한 X/Y 전략의 승률과 고전 최적 승률을 구분합니다.
- 3-5는 `(p=0,0.1,0.25,0.5)` 순서입니다. Alice에 발생한 Z 오류 여부는 공개하지 않습니다. GHZ+와 GHZ−를 각 확률로 섞은 상태에 **같은** 고정 전략을 사용해 각각 `(M,p_win)`을 계산합니다. 식과 우위 범위는 해당 문항의 실험 메모에 적습니다.

2-1·2-3·3-3·3-4·3-5의 수치 반환값은 이상적 회로의 정확한 값입니다. 고정 counts나 shots 추정값 일치를 요구하지 않습니다. 노트북의 4096-shot 관찰 결과는 따로 비교·기록하세요. 채점 절대 허용오차는 `1e-6`입니다.

`local_basis`의 여섯 회로는 모든 게임 입력을 평가하기 전에 각각 한 번씩 수집합니다. 제출 함수는 자신에게 전달되지 않은 테스트 상태·다른 사람의 입력·채점기 내부 상태를 참조하지 않습니다.

실수여야 하는 기댓값 계산에 복소 NumPy dtype을 사용해도 됩니다. 허수부가 절대 허용오차 `1e-6` 이하인 수치 오차이면 실수부로 비교하고, 그보다 큰 허수부는 오답으로 처리합니다.
