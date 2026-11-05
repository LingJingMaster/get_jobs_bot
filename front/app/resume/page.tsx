'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { FilePenLine } from 'lucide-react'
import PageHeader from '@/app/components/PageHeader'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { API_BASE } from '@/lib/api'

type Job = { id: number; jobName: string; companyName: string; jobDescription?: string }
type Version = { id: string; jobId: number; jobName: string; companyName: string; original: string; builder: string; resume: string; notes: string; jd: string; status: string; humanized: boolean }
async function result(response: Response) {
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败，请检查输入或 AI 设置')
  return data
}
export default function ResumePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [versions, setVersions] = useState<Version[]>([])
  const [jobId, setJobId] = useState('')
  const [source, setSource] = useState('')
  const [humanize, setHumanize] = useState(false)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [version, setVersion] = useState<Version | null>(null)
  const [edited, setEdited] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [generation, setGeneration] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [generationHumanize, setGenerationHumanize] = useState(false)
  useEffect(() => {
    if (generation !== 'running') return
    const started = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [generation])
  const job = jobs.find(j => String(j.id) === jobId)
  useEffect(() => {
    Promise.all([fetch(`${API_BASE}/api/boss/list?size=1000`).then(result), fetch(`${API_BASE}/api/resume-workflow`).then(result)])
      .then(([j, v]) => { setJobs(j.data || j.records || j.items || []); setVersions(v.items) })
      .catch(e => setMessage(e.message))
  }, [])
  const selectVersion = (v: Version) => { setVersion(v); setEdited(v.resume); setConfirmed(false) }
  const upload = async (file?: File) => {
    if (!file) return
    setBusy('正在提取简历文字'); setMessage('')
    try {
      const data = new FormData(); data.append('file', file)
      const value = await result(await fetch(`${API_BASE}/api/resume-workflow/extract`, { method: 'POST', body: data }))
      setSource(value.text); setMessage('已提取文字，请核对姓名、经历、日期和数字后再生成。')
    } catch (e) { setMessage((e as Error).message) } finally { setBusy('') }
  }
  const generate = async () => {
    if (busy) return
    setGeneration('running'); setElapsed(0); setGenerationHumanize(humanize)
    setBusy(humanize ? '正在执行 Resume Builder → Humanizer-zh，可能需要一至两分钟' : '正在执行 Resume Builder'); setMessage('')
    try {
      const value = await result(await fetch(`${API_BASE}/api/resume-workflow/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jobId: Number(jobId), resume: source, humanize }) }))
      setVersions(prev => [value, ...prev]); selectVersion(value)
      setMessage('草稿已保存。请对照原简历核对事实，补齐占位符后确认。')
      setGeneration('done')
    } catch (e) { setMessage((e as Error).message); setGeneration('error') } finally { setBusy('') }
  }
  const approve = async () => {
    if (!version) return
    setBusy('正在保存确认版本并生成投递图片'); setMessage('')
    try {
      const value = await result(await fetch(`${API_BASE}/api/resume-workflow/${version.id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume: edited }) }))
      setVersion(value); setVersions(prev => prev.map(v => v.id === value.id ? value : v)); setMessage('版本已确认，可以去投递页面预览并发送。')
    } catch (e) { setMessage((e as Error).message) } finally { setBusy('') }
  }
  return <div className="space-y-6">
    <PageHeader icon={<FilePenLine />} title="优化简历" subtitle="用原简历和选定岗位的 JD 生成专属版本，再核对并确认" actions={<Link className="text-link" href="/env-config">AI 服务设置</Link>} />
    <Card><CardHeader><CardTitle>1. 选择目标岗位</CardTitle><CardDescription>这里只使用已采集的真实 JD，不会把岗位要求写成你的经历。</CardDescription></CardHeader><CardContent>
      <label htmlFor="target-job" className="block mb-2">岗位</label>
      <select id="target-job" className="ui-field w-full p-3" value={jobId} onChange={e => setJobId(e.target.value)} disabled={!!busy}>
        <option value="">请选择岗位</option>{jobs.map(j => <option key={j.id} value={j.id}>{j.companyName} · {j.jobName}{j.jobDescription ? '' : '（缺少 JD）'}</option>)}
      </select>
      {!jobs.length && <p className="mt-3 text-muted-foreground">还没有岗位。<Link className="text-link" href="/boss">先去采集 JD</Link></p>}
      {job && <details className="mt-4"><summary className="cursor-pointer">查看岗位 JD</summary><p className="whitespace-pre-wrap mt-3 text-sm">{job.jobDescription || '该岗位缺少 JD，请重新采集。'}</p></details>}
    </CardContent></Card>
    <Card><CardHeader><CardTitle>2. 提供原简历</CardTitle><CardDescription>上传 PDF、DOCX、TXT 或 Markdown，或粘贴正文。文件在本机提取；点击生成后，简历与 JD 会发送给你配置的 AI 服务。</CardDescription></CardHeader><CardContent className="space-y-4">
      <input aria-label="上传原简历" type="file" accept=".pdf,.docx,.txt,.md" disabled={!!busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} />
      <Textarea aria-label="原简历正文" rows={12} value={source} onChange={e => setSource(e.target.value)} placeholder="姓名、工作经历、教育背景，以及你能确认的项目成果……" disabled={!!busy} />
      <label className="select-option"><input className="ui-checkbox" type="checkbox" checked={humanize} onChange={e => setHumanize(e.target.checked)} disabled={!!busy} />生成后运行 Humanizer-zh，保留事实并优化表达</label>
      <Button onClick={generate} disabled={!!busy || !job?.jobDescription || source.trim().length < 20}>{generation === 'running' ? '正在生成简历…' : '生成岗位专属简历'}</Button>
      {generation !== 'idle' && <div className="resume-generation-progress" aria-busy={generation === 'running'}>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span role="status">{generation === 'running' ? '正在处理，请稍候' : generation === 'done' ? '生成完成，草稿已保存' : '生成未完成，请查看下方错误信息后重试'}</span>
          <span className="text-muted-foreground tabular-nums">{generation === 'running' ? '已等待' : '用时'} {elapsed} 秒</span>
        </div>
        {generation !== 'error' && <progress className="resume-generation-bar" aria-label="简历生成进度" max={1} value={generation === 'done' ? 1 : undefined} />}
        <p className="text-xs text-muted-foreground leading-6">本次流程：Resume Builder 生成草稿{generationHumanize ? ' → Humanizer-zh 优化表达' : ''} → 保存版本。{generation === 'running' && '模型未提供实时百分比，请保持页面打开。'}</p>
      </div>}
    </CardContent></Card>
    <p role="status" className="text-sm whitespace-pre-wrap">{busy || message}</p>
    {!!versions.length && <Card><CardHeader><CardTitle>3. 核对版本</CardTitle><CardDescription>Builder 原稿会保留。确认后冻结版本，修改时请重新生成。</CardDescription></CardHeader><CardContent className="space-y-4">
      <select aria-label="简历版本" className="ui-field w-full p-3" value={version?.id || ''} disabled={!!busy} onChange={e => { const v = versions.find(v => v.id === e.target.value); if (v) selectVersion(v) }}><option value="">选择历史版本</option>{versions.map(v => <option value={v.id} key={v.id}>{v.companyName} · {v.jobName} · {v.status === 'approved' ? '已确认' : '草稿'} · {v.id.slice(0, 6)}</option>)}</select>
      {version && <>
        <p className="text-sm">处理流程：Resume Builder{version.humanized ? ' → Humanizer-zh' : ''}</p>
        <details><summary className="cursor-pointer">原简历与 Builder 原稿</summary><div className="grid lg:grid-cols-2 gap-4 mt-3"><pre className="whitespace-pre-wrap text-sm">{version.original}</pre><pre className="whitespace-pre-wrap text-sm">{version.builder}</pre></div></details>
        <Textarea aria-label="新版简历正文" rows={18} value={edited} readOnly={version.status === 'approved'} disabled={!!busy} onChange={e => { setEdited(e.target.value); setConfirmed(false) }} />
        <details open><summary>优化说明与待补充信息</summary><p className="whitespace-pre-wrap text-sm mt-3">{version.notes}</p></details>
        <div className="flex flex-wrap gap-4"><a className="text-link" href={`${API_BASE}/api/resume-workflow/${version.id}/download/html`}>下载已保存 HTML</a><a className="text-link" href={`${API_BASE}/api/resume-workflow/${version.id}/download/docx`}>下载已保存 Word</a></div>
        {version.status === 'draft' ? <><label className="select-option"><input type="checkbox" className="ui-checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />已核对经历、日期、数字和联系方式，并补齐占位符</label><Button onClick={approve} disabled={!confirmed || !!busy}>确认并生成投递图片</Button><p className="text-xs text-muted-foreground">此处编辑在确认时保存；下载按钮导出当前已保存版本。</p></> : <Link className="text-link" href="/delivery">前往投递与沟通</Link>}
      </>}
    </CardContent></Card>}
    <aside className="resume-workflow-note" aria-label="简历优化流程说明">
      <div>
        <p className="resume-workflow-note-title">流程说明</p>
        <p>采集岗位 JD → 上传并核对原简历 → Resume Builder 按岗位生成草稿 → 可选用 Humanizer-zh 优化表达 → 你核对确认 → 生成投递版本。</p>
      </div>
      <div className="resume-workflow-note-skills">
        <span>使用的开源 Skill</span>
        <a href="https://github.com/Jichengyuuuuu/resume-builder-skill" target="_blank" rel="noreferrer">Resume Builder</a>
        <a href="https://github.com/op7418/humanizer-zh" target="_blank" rel="noreferrer">Humanizer-zh</a>
      </div>
    </aside>
  </div>
}
