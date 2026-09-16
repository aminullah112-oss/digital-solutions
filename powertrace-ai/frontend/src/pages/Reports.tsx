import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Download, FileText } from 'lucide-react'
import { getToken } from '@/lib/api'
import { apiUrl } from '@/lib/config'
import { useApi, useSelectedProject } from '@/lib/hooks'
import { formatDateTime } from '@/lib/format'
import { Empty, Panel, SafetyNotice, Spinner } from '@/components/ui'

interface ReportRow {
  id: number; project_id: number; title: string; technician: string
  generated_at: string; diagnostic_session_id: number | null
}

export function Reports() {
  const [projectId] = useSelectedProject()
  const [params] = useSearchParams()
  const { data, loading } = useApi<ReportRow[]>(
    projectId ? `/api/reports?project_id=${projectId}` : '/api/reports')
  const [preview, setPreview] = useState<number | null>(
    params.get('open') ? Number(params.get('open')) : null)

  if (loading && !data) return <Spinner />

  return (
    <div className="space-y-4">
      <Panel title="Troubleshooting reports" dense>
        {!data?.length ? (
          <Empty icon={FileText} title="No reports"
            hint="Generate one from a diagnostic session." />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Title</th>
                <th className="th">Session</th>
                <th className="th">Technician</th>
                <th className="th">Generated</th>
                <th className="th w-px">Export</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="table-row">
                  <td className="td">
                    <button className="text-slate-100 hover:text-blue-300"
                      onClick={() => setPreview(r.id)}>
                      {r.title}
                    </button>
                  </td>
                  <td className="td text-xs text-slate-500">
                    {r.diagnostic_session_id ? `#${r.diagnostic_session_id}` : '—'}
                  </td>
                  <td className="td text-xs text-slate-400">{r.technician}</td>
                  <td className="td text-2xs text-slate-500">
                    {formatDateTime(r.generated_at)}
                  </td>
                  <td className="td">
                    <div className="flex gap-1.5">
                      {(['json', 'csv', 'pdf'] as const).map((format) => (
                        <DownloadButton key={format} id={r.id} format={format} />
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <SafetyNotice tone="info">
        Reports carry the provenance of every value: a measurement is labelled MEASURED, a
        controller reading CONTROLLER, and a simulated value SIMULATED. A report generated in
        demo mode is stamped as such on every page.
      </SafetyNotice>

      {preview && <ReportPreview id={preview} onClose={() => setPreview(null)} />}
    </div>
  )
}

function DownloadButton({ id, format }: { id: number; format: 'json' | 'csv' | 'pdf' }) {
  const [error, setError] = useState<string | null>(null)
  const download = async () => {
    const token = getToken()
    const response = await fetch(apiUrl(`/api/reports/${id}?format=${format}`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      setError(body?.detail ?? `Export failed (${response.status})`)
      setTimeout(() => setError(null), 8000)
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `report-${id}.${format}`
    link.click()
    URL.revokeObjectURL(url)
  }
  return (
    <span className="relative">
      <button className="btn py-0.5 text-[10px]" onClick={() => void download()}>
        <Download className="h-3 w-3" /> {format.toUpperCase()}
      </button>
      {error && (
        <span className="absolute right-0 top-7 z-20 w-72 rounded border border-amber-700/50
          bg-amber-950/90 px-2 py-1.5 text-[10px] text-amber-200">
          {error}
        </span>
      )}
    </span>
  )
}

function ReportPreview({ id, onClose }: { id: number; onClose: () => void }) {
  const [html, setHtml] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    fetch(apiUrl(`/api/reports/${id}?format=html`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then((r) => r.text()).then(setHtml)
  }, [id])

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6"
      onClick={onClose}>
      <div className="panel w-full max-w-4xl h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider">
            Report preview — print to PDF from here
          </h2>
          <button className="btn py-1" onClick={onClose}>Close</button>
        </div>
        <div className="flex-1 bg-white overflow-hidden">
          {html === null ? <Spinner /> : (
            <iframe srcDoc={html} title="Report" className="w-full h-full" />
          )}
        </div>
      </div>
    </div>
  )
}
