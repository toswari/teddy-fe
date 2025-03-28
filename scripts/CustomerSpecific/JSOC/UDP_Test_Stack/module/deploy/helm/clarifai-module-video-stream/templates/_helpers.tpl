{{- define "ingressMergeAnnotations" -}}
{{- $className := .Values.ingress.className -}}
{{- $albAnnotations := .Values.ingress.defaultAnnotations.alb | default (dict) -}}
{{- $ingressNginxAnnotations := .Values.ingress.defaultAnnotations.ingressNginx | default (dict) -}}
{{- $annotations := .Values.ingress.annotations | default (dict) -}}
{{- $mergedAnnotations := $annotations }}
{{- if eq $className "alb" }}
{{- $mergedAnnotations := merge $annotations $albAnnotations -}}
{{- else }}
{{- $mergedAnnotations := merge $annotations $ingressNginxAnnotations -}}
{{- end }}
{{- if not (empty $mergedAnnotations) }}
{{- toYaml $mergedAnnotations -}}
{{- end -}}
{{- end -}}
