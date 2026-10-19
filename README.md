# GitOps Developer Platform

An initial, deliberately small command-line scaffold for turning one service definition into Kubernetes JSON manifests. It produces a Namespace, Deployment, and Service with HTTP health probes and explicit resource requests and limits. It can also emit example Flux `GitRepository` and `Kustomization` resources.

## Quick start

Requires Python 3.10 or later and uses only the Python standard library.

```sh
python3 platform.py scaffold examples/service.json --output generated/orders-api
```

To include Flux examples:

```sh
python3 platform.py scaffold examples/service.json \
  --output generated/orders-api \
  --flux-url https://github.com/example/platform-config.git \
  --flux-branch main
```

The command refuses to replace existing generated files. Pass `--force` when replacement is intentional. Run `python3 platform.py scaffold --help` for all options.

## Service definition

The required fields are `name`, `namespace`, `image`, and `containerPort`. The example also shows optional service port, replica count, health path, and resource settings. If resources are omitted, the generator supplies conservative placeholders that should be tuned for the workload.

Use an immutable image digest in a real delivery repository where reproducibility matters. The example tag is illustrative.

## Architecture

```text
service.json
     |
     v
platform.py  --->  Namespace + Deployment + Service
     |
     +-----------> optional Flux GitRepository + Kustomization
                              |
                              v
                     reviewed Git repository
                              |
                              v
                       Flux reconciliation
```

The CLI only renders files. Git remains the source of truth: a team reviews the generated manifests, places them at the path referenced by Flux, and merges them through its normal repository workflow. Flux then reconciles the approved state into a cluster.

## Suggested repository flow

1. Update the service definition or image reference.
2. Generate manifests into the intended environment directory.
3. Review the diff, especially probes, resources, namespace, Flux path, and image provenance.
4. Commit through the repository's normal review process.
5. Observe Flux and Kubernetes status using the operational tools already approved by the team.

## Rollback

Revert the Git commit that introduced the unwanted state, then merge the revert. Flux should reconcile the repository's previous desired state on its next interval. A rollback is not guaranteed to undo external effects such as database migrations, deleted persistent data, or calls to third-party systems; those need a service-specific recovery plan.

## Design decisions

- **Render before deployment.** A file generator keeps cluster credentials out of the tool and makes the desired state reviewable in Git. A direct deployment command would couple rendering to access and rollout policy.
- **One service definition.** A small JSON input reduces repeated configuration without introducing a template language. Helm remains a better fit when chart packaging and dependency management are required.
- **Flux as an optional integration.** Kubernetes resources remain usable independently. The generated Flux resources illustrate reconciliation; they do not provision a complete platform.

For production use, the next decisions are schema validation, image provenance, access policies, and promotion between environments. Observability and rollback verification belong to the operating environment.

## Status and limitations

- The generator performs basic input checks but does not validate manifests against Kubernetes or Flux schemas.
- It does not create ingress, autoscaling, policies, secrets, service accounts, or environment promotion workflows.
- Flux authentication and secret management are intentionally outside this example.
- The Flux path is a convention (`clusters/production/<service>`) and may need editing for a real repository layout.
- Probe timing and default resources are starting points, not production recommendations.
- Initial implementation; no local tests or Kubernetes/Flux validation have been performed.

## License

MIT. See [LICENSE](LICENSE).
