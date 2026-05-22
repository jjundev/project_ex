## KVL/KCL 검증 결과

### Topology 대조
- Fig 7.9: PASS. 교재 원도와 보고서 모두 source(+) -> C(0.47 uF) -> R -> GND 구조이며 Channel 2는 R 양단이다.
- Fig 7.11: PASS. 교재 원도와 보고서 모두 source(+) -> R -> C(0.47 uF) -> GND 구조이며 Channel 2는 C 양단이다.
- Fig 7.12: PASS. 교재 원도와 보고서 모두 Fig 7.9와 같은 R-C 직렬 회로이고, Channel 1 vertical = E, horizontal input = V_R이다. 이전 오류였던 y_m = V_R 해석은 수정되어 y_m = E_peak 기준으로 작성됨.
- Fig 8.1: PASS. source(+) -> L(10 mH) -> R(1 kOhm) -> GND 직렬 구조와 일치한다.
- Fig 8.2: PASS. source(+) -> C(0.01 uF) -> R(1 kOhm) -> GND 직렬 구조와 일치한다.
- Fig 8.3: PASS. source(+) -> R -> L -> C -> GND 직렬 구조이며 V_ab는 R 이후 노드 a와 GND 사이, 즉 L+C 합성 전압으로 해석되어 있다.
- Fig 9.1: PASS. R과 L이 전원 양단에 병렬 접속된 기본 R||L 구조와 일치한다.
- Fig 9.2: PASS. R_s가 R||L 병렬망 하단 귀환 경로에 직렬 삽입되어 총전류 I_s를 센싱하는 교재 구조와 일치한다.
- Fig 9.3: PASS. R_s가 인덕터 가지 내부에만 직렬 삽입되어 I_L을 센싱하는 교재 구조와 일치한다.

### 회로 1: Ch 7 R-C 직렬 위상 측정
- KVL: PASS. Table 7.1~7.6의 phasor KVL은 sqrt(V_R^2 + V_C^2) = 4 V로 성립한다.
- KCL: 해당 없음. 직렬 단일 루프 회로이며 전류 공통 조건으로 해석되어 있다.
- 계산/단위: PASS. E_(p-p)는 모두 4 V로 수정되어 이전 8 V/4 V 혼재 문제가 해소되었다. X_C, V_R, V_C, theta, D_1, D_2 계산도 허용 오차 내이다.
- Lissajous: PASS. Table 7.8은 vertical 축을 E로 두고 y_m = E_peak/(1 V/div) = 2 div로 계산하여 교재 Fig 7.12 축 해석과 일치한다.

### 회로 2: Ch 8 직렬 R-L, R-C, R-L-C
- KVL: PASS. Table 8.1, 8.3, 8.5는 각각 sqrt(V_R^2 + V_L^2), sqrt(V_R^2 + V_C^2), sqrt(V_R^2 + (V_L - V_C)^2) = 4 V 관계를 만족한다.
- KCL: 해당 없음. 직렬 회로이며 I_(p-p)가 공통 전류로 계산되어 있다.
- 계산/단위: PASS. X_L = 628.32 Ohm, X_C = 1591.55 Ohm, Z_T 및 전압 분배 계산은 이상적 소자 가정 기준으로 타당하다.

### 회로 3: Ch 9 병렬 R-L
- KVL: PASS. 병렬 가지 전압을 V_R = V_L = E = 4 V(p-p)로 두는 해석이 맞다. R_s는 이상 계산에서 무시한다는 가정이 명시되어 있다.
- KCL: PASS. Table 9.1에서 I_s = sqrt(I_R^2 + I_L^2) = sqrt(4.00^2 + 6.366^2) = 7.52 mA로 계산되어 KCL이 성립한다.
- 계산/단위: PASS. Table 9.2의 theta_L은 교재 Part 1(h)의 E와 I_L 사이 각으로 90.00 deg, D_2 = 1.25 div로 수정되었다. Table 9.4의 theta_L은 I_s와 I_L 사이 각 32.14 deg로 별도 정의되어 있어 이전 혼동이 해소되었다.

### 단위 일관성
- PASS. V, mV, mA, Ohm, kOhm, uF, div 단위가 표와 계산식에 대체로 명시되어 있다.
- 단, STT 실측 전류값은 RMS인지 p-p인지 보고서에서 대응 설명이 없어 STT 교차검증 항목에서 FAIL로 판정한다.

### STT 교차검증
- Ch 7: 부분 PASS. STT의 V_R/ V_C 실측값(예: Part 1의 약 2.0 V, 3.58 V, 3.94 V 및 Part 2의 약 3.5 V, 1.93 V, 1.05 V)은 보고서의 이상적 예측값과 큰 틀에서 근접한다. 다만 STT의 Lissajous y_o/y_m 발화는 불명확하고 교재 축 해석과 충돌 가능성이 있어, 보고서처럼 교재 Fig 7.12 기준을 우선한 처리는 타당하다.
- Ch 8: FAIL. STT에는 실제 측정값으로 보이는 값이 존재하나 보고서의 Measured 칼럼은 모두 이상적 계산값으로만 채워져 있고 STT와의 차이가 설명되지 않는다. 예: STT 8-1 V_R 약 3.3 V, V_L 약 2.9 V vs 보고서 3.39 V, 2.13 V; STT 8-3 V_C 약 4.34 V, V_L 약 1.61 V, V_ab 약 1.5 V vs 보고서 4.59 V, 1.81 V, 2.78 V.
- Ch 9: FAIL. STT 9-1에는 R_s 약 12.6 Ohm, V_Rs 약 80 mV / 68 mV, I_s 약 2.38 mA, I_R 약 1.2 mA, I_L 약 2.1 mA가 언급된다. 보고서는 R_s 명판값 10 Ohm과 이상적 p-p 계산값(I_s 7.52 mA, I_L 6.37 mA, I_R 4.00 mA, V_Rs 75.18 mV / 63.66 mV)만 제시하고, STT 전류값이 RMS인지 p-p인지 또는 V_Rs/R_s로 환산한 p-p 값과 어떻게 대응되는지 정리하지 않았다. 이전 STT 교차검증 FAIL 항목이 완전히 해소되지 않았다.

### 발견된 오류
- [STT 교차검증] Ch 8, Ch 9의 실제 STT 측정값과 보고서의 Measured 칼럼 사이 대응 설명이 없다. 특히 Ch 9는 STT의 R_s = 12.6 Ohm 및 V_Rs = 80 mV / 68 mV를 반영하거나 p-p/RMS 변환 관계를 명시해야 하나, 보고서는 명판값 10 Ohm 기반 이상값만 사용했다.
- [단위/측정값 대응] Ch 9 STT 전류값이 RMS/측정값일 가능성이 있는데 보고서의 p-p 예상값과 직접 비교할 수 있는 단위 변환 또는 주석이 없다.

최종 판정: FAIL
