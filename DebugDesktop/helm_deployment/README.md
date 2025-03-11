# Guacamole Desktop Helm Chart

This Helm chart deploys the Guacamole Desktop Container in a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- Ingress controller (if using ingress)
- Local registry or access to container registry
- PV provisioner support (if persistence is enabled)

## Installing the Chart

1. Load the Docker image to your local registry:
```bash
docker load -i guacamole.tar
docker tag guacamole localhost:5000/guacamole:latest
docker push localhost:5000/guacamole:latest
```

2. Install the chart:
```bash
helm install guacamole ./guacamole
```

To install with custom values:
```bash
helm install guacamole ./guacamole -f custom-values.yaml
```

## Configuration

The following table lists the configurable parameters of the chart and their default values:

| Parameter                  | Description                                     | Default                    |
|---------------------------|-------------------------------------------------|----------------------------|
| `image.repository`        | Image repository                                | `localhost:5000/guacamole` |
| `image.tag`              | Image tag                                       | `latest`                   |
| `image.pullPolicy`       | Image pull policy                               | `IfNotPresent`            |
| `service.type`           | Kubernetes service type                         | `ClusterIP`               |
| `service.guacamolePort`  | Guacamole service port                         | `8080`                    |
| `service.vncPort`        | VNC service port                               | `5901`                    |
| `ingress.enabled`        | Enable ingress                                 | `true`                    |
| `ingress.className`      | Ingress class name                             | `nginx`                   |
| `ingress.hosts`          | Ingress hosts                                  | `[guacamole.local]`       |
| `resources.requests.cpu` | CPU request                                    | `500m`                    |
| `resources.requests.memory` | Memory request                              | `1Gi`                     |
| `resources.limits.cpu`   | CPU limit                                      | `2000m`                   |
| `resources.limits.memory`| Memory limit                                   | `4Gi`                     |
| `persistence.enabled`    | Enable persistence                             | `false`                   |
| `persistence.size`       | PVC size                                       | `10Gi`                    |
| `persistence.storageClass` | PVC storage class                            | `""`                      |

## Example Values File

```yaml
image:
  repository: my-registry.com/guacamole
  tag: v1.0.0

service:
  type: LoadBalancer

ingress:
  enabled: true
  hosts:
    - host: guacamole.example.com
      paths:
        - path: /
          pathType: Prefix

persistence:
  enabled: true
  storageClass: standard

resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 4000m
    memory: 8Gi
```

## Accessing the Application

1. Via Ingress:
   - Access through your configured hostname (e.g., `http://guacamole.local`)

2. Via Port-Forward:
```bash
kubectl port-forward svc/guacamole-guacamole 8080:8080
```
Then access `http://localhost:8080/guacamole`

## Default Credentials

- Guacamole Web Interface:
  - Username: `admin`
  - Password: `admin`

## Persistence

If persistence is enabled, the user home directory (`/home/vnc_user`) will be persisted using a PVC.

## Security Considerations

- The container runs in privileged mode by default
- Default credentials should be changed for production use
- Consider implementing network policies
- Use HTTPS for ingress in production

## Uninstalling the Chart

```bash
helm uninstall guacamole
```

## Troubleshooting

1. Check pod status:
```bash
kubectl get pods -l app.kubernetes.io/name=guacamole
```

2. View pod logs:
```bash
kubectl logs -l app.kubernetes.io/name=guacamole
```

3. Common issues:
   - Image pull errors: Verify registry access
   - Resource limits: Adjust if pods are being OOMKilled
   - Ingress issues: Verify ingress controller and DNS configuration
