FROM ubuntu:24.04

ARG RUNNER_VERSION=2.332.0
ARG KUBECTL_VERSION=1.35.2
ARG SOPS_VERSION=3.12.1
ARG KUSTOMIZE_VERSION=5.8.1
ARG TARGETARCH=arm64

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git jq make python3 python3-pip python3-venv \
    gnupg apt-transport-https libicu74 \
    && rm -rf /var/lib/apt/lists/*

# kubectl
RUN curl -fsSL "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
    -o /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl

# kustomize
RUN curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_${TARGETARCH}.tar.gz" \
    | tar xz -C /usr/local/bin/

# sops
RUN curl -fsSL "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${TARGETARCH}" \
    -o /usr/local/bin/sops && chmod +x /usr/local/bin/sops

# doppler
RUN curl -fsSL https://cli.doppler.com/install.sh | sh

# GitHub Actions runner
RUN useradd -m -d /home/runner runner \
    && mkdir -p /home/runner/actions-runner \
    && cd /home/runner/actions-runner \
    && curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${TARGETARCH}-${RUNNER_VERSION}.tar.gz" \
    | tar xz \
    && chown -R runner:runner /home/runner

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER runner
WORKDIR /home/runner/actions-runner

ENTRYPOINT ["/entrypoint.sh"]
