{{/*
Common naming helpers.
*/}}
{{- define "ivs.name" -}}
{{- default "internet-voting-system" .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ivs.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "ivs.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "ivs.labels" -}}
app.kubernetes.io/name: {{ include "ivs.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "ivs.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ivs.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "ivs.api.args" -}}
- "--host"
- "0.0.0.0"
- "--port"
- "8787"
- "--storage"
- {{ .Values.storage.backend | quote }}
{{- if eq .Values.storage.backend "sqlite" }}
- "--sqlite-path"
- "/data/voting.sqlite3"
{{- end }}
{{- if eq .Values.storage.backend "postgres" }}
- "--dsn"
- "$(IVS_PG_DSN)"
{{- end }}
{{- end -}}
