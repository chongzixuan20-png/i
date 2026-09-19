import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  ClipboardCheck,
  FileSearch,
  Inbox,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  UsersRound,
} from 'lucide-react'
import './index.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080'

const nav = [
  { name: 'Inbox', icon: Inbox },
  { name: 'Compare documents', icon: FileSearch },
  { name: 'Review queue', icon: UsersRound },
]

function App() {
  const [page, setPage] = useState('Inbox')
  const [emails, setEmails] = useState([])
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [report, setReport] = useState(null)
  const [files, setFiles] = useState({ si: null, bl: null })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadInbox = async () => {
    try {
      const response = await fetch(`${API}/api/inbox`)
      if (!response.ok) throw new Error('API unavailable')
      const data = await response.json()
      setEmails(data)
      setError('')
    } catch (err) {
      setError('The backend is not running. Start FastAPI on port 8080 first.')
    }
  }

  useEffect(() => {
    loadInbox()
  }, [])

  async function demoVerify(id) {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API}/api/verify/demo/${id}`, { method: 'POST' })
      if (!response.ok) throw new Error('demo verification failed')
      const data = await response.json()
      setReport(data)
      setPage('Compare documents')
    } catch (err) {
      setError('Could not run the demo verification. Check the backend connection.')
    } finally {
      setBusy(false)
    }
  }

  async function uploadVerify() {
    if (!files.si || !files.bl) {
      setError('Select both an SI and BL file before running verification.')
      return
    }

    setBusy(true)
    setError('')

    try {
      const form = new FormData()
      form.append('si', files.si)
      form.append('bl', files.bl)

      const response = await fetch(`${API}/api/verify/upload`, {
        method: 'POST',
        body: form,
      })

      if (!response.ok) throw new Error('upload verification failed')
      const data = await response.json()
      setReport(data)
    } catch (err) {
      setError('The documents could not be processed. Check the FastAPI API and file format.')
    } finally {
      setBusy(false)
    }
  }

  const checkEmails = emails.filter((email) => email.category === 'document-comparison request')

  return (
    <div className="min-h-screen flex bg-[#f5f8f7] text-[#183536]">
      <aside className="w-64 shrink-0 bg-[#183536] text-white p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-12">
          <div className="h-9 w-9 rounded-xl bg-[#f2b84b] text-[#183536] grid place-items-center font-black">◈</div>
          <div>
            <div className="font-bold tracking-wide">INSCOUT</div>
            <div className="text-xs text-[#a9c0bd]">shipment desk</div>
          </div>
        </div>

        <div className="text-xs uppercase tracking-[.18em] text-[#91aaa6] mb-4">Workspace</div>
        <div className="space-y-2">
          {nav.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.name}
                onClick={() => setPage(item.name)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left ${
                  page === item.name ? 'bg-[#2a5250] text-white' : 'text-[#b4c8c5] hover:bg-[#214644]'
                }`}
              >
                <Icon size={17} />
                {item.name}
              </button>
            )
          })}
        </div>

        <div className="mt-auto text-xs text-[#91aaa6] border-t border-[#315350] pt-5">
          FastAPI · Gemini · Firestore
        </div>
      </aside>

      <main className="flex-1 p-8 max-w-6xl">
        <header className="flex justify-between items-start mb-8">
          <div>
            <div className="text-xs font-bold tracking-[.18em] text-[#258276] uppercase mb-2">
              Operations workspace
            </div>
            <h1 className="text-3xl font-semibold text-[#183536]">{page}</h1>
            <p className="text-[#6b7d7c] mt-2">
              Keep document checks moving without losing the human judgment behind them.
            </p>
          </div>

          <button
            onClick={loadInbox}
            className="border border-[#d5e1df] bg-white rounded-lg px-3 py-2 text-sm text-[#46615f] flex gap-2 items-center"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </header>

        {error && (
          <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {page === 'Inbox' && (
          <>
            <div className="grid grid-cols-3 gap-4 mb-7">
              {[
                ['Inbox today', emails.length],
                ['Checks found', checkEmails.length],
                ['System', 'Ready'],
              ].map(([label, value]) => (
                <div key={label} className="bg-white border border-[#e0e9e7] rounded-xl p-5">
                  <div className="text-sm text-[#718482]">{label}</div>
                  <div className="text-2xl font-semibold mt-2">{value}</div>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              {emails.map((email) => (
                <div
                  key={email.id}
                  className="bg-white border border-[#e0e9e7] rounded-xl p-5 flex items-center gap-5"
                >
                  <div className="h-10 w-10 rounded-full bg-[#eaf3f0] text-[#258276] grid place-items-center">
                    <ClipboardCheck size={18} />
                  </div>

                  <div className="flex-1">
                    <div className="font-semibold">{email.subject}</div>
                    <div className="text-sm text-[#718482] mt-1">
                      {email.sender} · {email.id}
                    </div>
                    <div className="text-sm text-[#526967] mt-3">{email.preview}</div>
                  </div>

                  <div className="text-right">
                    <span className="text-xs rounded-full bg-[#eef5ed] text-[#287467] px-2.5 py-1">
                      {email.category}
                    </span>
                    <div className="text-xs text-[#829390] mt-3">
                      {email.attachments?.length || 0} attachment(s)
                    </div>
                    {email.category === 'document-comparison request' && (
                      <button
                        onClick={() => demoVerify(email.id)}
                        className="mt-3 text-sm font-semibold text-[#258276]"
                      >
                        Open check →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {page === 'Compare documents' && (
          <div className="space-y-5">
            <div className="bg-white border border-[#e0e9e7] rounded-xl p-6">
              <div className="font-semibold mb-1">Run a document check</div>
              <div className="text-sm text-[#718482] mb-5">
                Plain text and text-based PDFs are supported.
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <label className="border-2 border-dashed border-[#cbdcd8] rounded-xl p-5 text-sm">
                  <div className="flex gap-2 items-center font-medium">
                    <UploadCloud size={17} />
                    Shipping Instruction (SI)
                  </div>
                  <input
                    className="mt-4 w-full text-xs"
                    type="file"
                    accept=".txt,.pdf"
                    onChange={(e) => setFiles((prev) => ({ ...prev, si: e.target.files?.[0] || null }))}
                  />
                </label>

                <label className="border-2 border-dashed border-[#cbdcd8] rounded-xl p-5 text-sm">
                  <div className="flex gap-2 items-center font-medium">
                    <UploadCloud size={17} />
                    Bill of Lading (BL)
                  </div>
                  <input
                    className="mt-4 w-full text-xs"
                    type="file"
                    accept=".txt,.pdf"
                    onChange={(e) => setFiles((prev) => ({ ...prev, bl: e.target.files?.[0] || null }))}
                  />
                </label>
              </div>

              <button
                disabled={busy}
                onClick={uploadVerify}
                className="mt-5 bg-[#e46d55] text-white rounded-lg px-5 py-2.5 font-medium disabled:opacity-50"
              >
                {busy ? 'Checking…' : 'Run verification'}
              </button>
            </div>

            {report && <VerificationReport report={report} />}
          </div>
        )}

        {page === 'Review queue' && (
          <div className="bg-white border border-[#e0e9e7] rounded-xl p-8 text-center">
            <ShieldCheck className="mx-auto text-[#258276]" size={30} />
            <div className="font-semibold mt-3">Review queue is connected</div>
            <p className="text-sm text-[#718482] mt-2">
              Run a check with low confidence or a mismatch to create a review item. Firestore persistence is enabled when configured.
            </p>
          </div>
        )}
      </main>
    </div>
  )
}

function VerificationReport({ report }) {
  return (
    <div className="bg-white border border-[#e0e9e7] rounded-xl p-6">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-xs uppercase tracking-widest text-[#258276] font-bold">
            Verification report
          </div>
          <h2 className="text-xl font-semibold mt-2">{report.result}</h2>
        </div>

        <div className="text-right">
          <div className="text-2xl font-semibold">{report.confidence}%</div>
          <div className="text-xs text-[#718482]">confidence</div>
        </div>
      </div>

      {report.needs_human_review && (
        <div className="mt-4 rounded-lg bg-[#fff6df] text-[#856421] p-3 text-sm">
          Needs human review: {report.review_reason || 'Please confirm the discrepancy.'}
        </div>
      )}

      <div className="overflow-auto mt-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[#718482] border-b">
              <th className="py-3">Field</th>
              <th>SI</th>
              <th>BL</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {report.fields.map((row) => (
              <tr key={row.field} className="border-b border-[#edf2f1]">
                <td className="py-3 font-medium">{row.label}</td>
                <td>{row.si ?? '—'}</td>
                <td>{row.bl ?? '—'}</td>
                <td className={row.match ? 'text-[#258276]' : 'text-[#d45e4c]'}>
                  {row.match ? 'Match' : 'Mismatch'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
