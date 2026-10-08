---
layout: software
title: Software
permalink: /software/

# This is a deliberately short list of selected research software.
# Copy an entry below to add a new project. `image` is optional.
# `projects` is optional: use `[anr]`, `[erc]`, or `[anr, erc]` to show an
# item on the corresponding project page. Leave it empty for main-site only.
software:
  - category: "Selected software"
    entries:
      - title: "MLXP"
        description: "Launch experiment sweeps, record configurations, code versions and artifacts, and query results in one Python workflow. MLXP supports cluster job submission and makes experiments easier to reproduce. ACM REP 2024."
        code_url: "https://github.com/inria-thoth/mlxp"
        docs_url: "https://inria-thoth.github.io/mlxp/pages/master/index.html"
        paper_url: "https://arxiv.org/abs/2402.13831"
        projects: [anr]
      - title: "EquiTabPFN"
        description: "A tabular foundation model whose predictions respect class-label permutations, avoiding costly permutation ensembling and accommodating more classes than seen during pretraining. Includes training and benchmark code. NeurIPS 2025."
        code_url: "https://github.com/MichaelArbel/EquiTabPFN"
        paper_url: "https://arxiv.org/abs/2502.06684"
        projects: [anr]
      - title: "funcBO"
        description: "Functional bilevel optimization with neural-network inner models, without requiring strong convexity in their parameters. Includes instrumental-regression experiments and baselines to reproduce and extend the method. NeurIPS 2024 · Spotlight."
        code_url: "https://github.com/inria-thoth/funcBO"
        paper_url: "https://arxiv.org/abs/2403.20233"
        projects: [anr]
      - title: "BGS-opt"
        description: "Implementations of AmIGO and Bilevel Games with Selection for differentiating through optimization. Reproduce quadratic benchmarks, large-scale hyperparameter optimization, and CIFAR-10 dataset distillation. ICLR 2022, NeurIPS 2022."
        code_url: "https://github.com/MichaelArbel/BGS-opt"
        paper_url: "https://arxiv.org/abs/2207.04888"
        projects: []
---
