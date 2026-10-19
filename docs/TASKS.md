# Tasks

Open tasks of the project. Each one is a GitHub issue with its acceptance criteria. To take one, comment on the issue (or tell Salim its number).

Status of the project: the engine is frozen (`PHASE_4_FROZEN`) and the decision is **NO-GO (provisional)** until a lawyer validates the answers (T1). Code tasks must not modify the frozen engine; engine ideas are written as proposals for the next freeze.

| Task | Title | Difficulty | Depends on | Issue |
|---|---|---|---|---|
| T1 | Legal validation of the answers and the benchmark | hard | none | [#1](https://github.com/SalimMabed/regassist-dz/issues/1) |
| T2 | TEST v2: an independent test written by a lawyer | medium | T1 | [#2](https://github.com/SalimMabed/regassist-dz/issues/2) |
| T3 | Review and merge the Linux/VPS deployment branch | medium | none | [#3](https://github.com/SalimMabed/regassist-dz/issues/3) |
| T4 | Fix the replication package (vector keys) and prove it on a clean machine | medium | T3 | [#4](https://github.com/SalimMabed/regassist-dz/issues/4) |
| T5 | Public deployment on a VPS | hard | T3, T4 | [#5](https://github.com/SalimMabed/regassist-dz/issues/5) |
| T6 | Repository governance: visibility, licence, credits, privacy | easy | none | [#6](https://github.com/SalimMabed/regassist-dz/issues/6) |
| T7 | Bridge everyday terms and corpus terms | medium | T1 | [#7](https://github.com/SalimMabed/regassist-dz/issues/7) |
| T8 | Measure the definition guard | easy | none | [#8](https://github.com/SalimMabed/regassist-dz/issues/8) |
| T9 | Study: outdated amounts when an article was amended (proposal for the next freeze) | hard | none | [#9](https://github.com/SalimMabed/regassist-dz/issues/9) |
| T10 | Study: answer or refusal flips near the similarity threshold (proposal for the next freeze) | hard | none | [#10](https://github.com/SalimMabed/regassist-dz/issues/10) |
| T11 | Continuous integration with GitHub Actions | easy | none | [#11](https://github.com/SalimMabed/regassist-dz/issues/11) |
| T12 | Prepare the demo and collect feedback | easy | none | [#12](https://github.com/SalimMabed/regassist-dz/issues/12) |

Order of work: T1 and T3 can start now. T2 and T7 wait for T1. T4 and T5 wait for T3. T6, T8 to T12 are independent.
