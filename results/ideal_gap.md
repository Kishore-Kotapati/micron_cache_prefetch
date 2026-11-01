### How close to a perfect cache

| Trace | Baseline cycles | Final cycles | Perfect-cache cycles | Speedup now | Max possible | Share of possible gain achieved |
|---|---|---|---|---|---|---|
| sequential | 112571 | 29172 | 28603 | 3.86× | 3.94× | 99.3 % |
| stride | 133557 | 25688 | 10557 | 5.20× | 12.65× | 87.7 % |
| random | 177688 | 177688 | 14140 | 1.00× | 12.57× | 0.0 % |
| repeated | 17357 | 16127 | 13421 | 1.08× | 1.29× | 31.2 % |
| mixed | 182100 | 86455 | 21096 | 2.11× | 8.63× | 59.4 % |
| capacity | 84464 | 22016 | 21488 | 3.84× | 3.93× | 99.2 % |
| cnn | 112549 | 51680 | 42931 | 2.18× | 2.62× | 87.4 % |
| llm | 82323 | 29855 | 29025 | 2.76× | 2.84× | 98.4 % |
| recsys | 79479 | 54379 | 33562 | 1.46× | 2.37× | 54.7 % |
