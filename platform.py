#!/usr/bin/env python3
"""Generate a small GitOps-ready Kubernetes service scaffold from JSON."""

import argparse
import json
import re
import sys
from pathlib import Path


DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    required = {"name", "namespace", "image", "containerPort"}
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    for field in ("name", "namespace"):
        value = config[field]
        if not isinstance(value, str) or len(value) > 63 or not DNS_LABEL.fullmatch(value):
            raise ValueError(f"{field} must be a Kubernetes DNS label")
    port = config["containerPort"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("containerPort must be an integer from 1 to 65535")
    return config


def manifests(config: dict, flux_url: str | None, flux_branch: str) -> dict[str, dict]:
    name = config["name"]
    namespace = config["namespace"]
    port = config["containerPort"]
    labels = {"app.kubernetes.io/name": name, "app.kubernetes.io/managed-by": "gitops-platform-cli"}
    probe_path = config.get("healthPath", "/healthz")
    replicas = config.get("replicas", 2)
    resources = config.get(
        "resources",
        {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}},
    )
    output = {
        "namespace.json": {
            "apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}
        },
        "deployment.json": {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app.kubernetes.io/name": name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {"containers": [{
                        "name": name,
                        "image": config["image"],
                        "ports": [{"name": "http", "containerPort": port}],
                        "readinessProbe": {"httpGet": {"path": probe_path, "port": "http"}, "initialDelaySeconds": 5, "periodSeconds": 10},
                        "livenessProbe": {"httpGet": {"path": probe_path, "port": "http"}, "initialDelaySeconds": 15, "periodSeconds": 20},
                        "resources": resources,
                    }]},
                },
            },
        },
        "service.json": {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {"selector": {"app.kubernetes.io/name": name}, "ports": [{"name": "http", "port": config.get("servicePort", 80), "targetPort": "http"}]},
        },
    }
    if flux_url:
        output["flux-source.json"] = {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {"name": name, "namespace": "flux-system"},
            "spec": {"interval": "1m", "url": flux_url, "ref": {"branch": flux_branch}},
        }
        output["flux-kustomization.json"] = {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {"name": name, "namespace": "flux-system"},
            "spec": {
                "interval": "10m",
                "path": f"./clusters/production/{name}",
                "prune": True,
                "wait": True,
                "sourceRef": {"kind": "GitRepository", "name": name},
            },
        }
    return output


def write_files(items: dict[str, dict], destination: Path, force: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    collisions = [destination / name for name in items if (destination / name).exists()]
    if collisions and not force:
        names = ", ".join(path.name for path in collisions)
        raise FileExistsError(f"refusing to overwrite {names}; pass --force to replace generated files")
    for filename, document in items.items():
        (destination / filename).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scaffold = subparsers.add_parser("scaffold", help="generate Kubernetes JSON manifests")
    scaffold.add_argument("config", type=Path, help="service configuration JSON")
    scaffold.add_argument("--output", type=Path, required=True, help="destination directory")
    scaffold.add_argument("--flux-url", help="also generate Flux resources for this Git URL")
    scaffold.add_argument("--flux-branch", default="main", help="Flux source branch (default: main)")
    scaffold.add_argument("--force", action="store_true", help="replace generated files that already exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        write_files(manifests(config, args.flux_url, args.flux_branch), args.output, args.force)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote manifests to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
