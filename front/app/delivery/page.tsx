'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Send } from 'lucide-react'
import PageHeader from '@/app/components/PageHeader'
import AnalysisContent from '@/app/boss/analysis/AnalysisContent'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { API_BASE } from '@/lib/api'

type Version = { id: string; jobName: string; companyName: string; status: string }
type Status = { running?: boolean; isLoggedIn?: boolean; message?: string; challenge?: boolean }
export default function DeliveryPage() {
  const [versions, setVersions] = useState<Version[]>([])
  const [version, setVersion] = useState('')
  const [greeting, setGreeting] = useState('您好，我对这个岗位很感兴趣，附上简历，期待进一步沟通。')
  const [status, setStatus] = useState<Status>({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewed, setPreviewed] = useState(false)
  useEffect(() => {
    fetch(`${API_BASE}/api/resume-workflow`).then(r => r.json()).then(v => setVersions((v.items || []).filter((v: Version) => v.status === 'approved'))).catch(() => setMessage('无法加载简历版本'))
    const update = () => fetch(`${API_BASE}/api/boss/status`).then(r => r.json()).then(setStatus).catch(() => setMessage('后端未连接'))
    void update(); const timer = setInterval(update, 3000); return () => clearInterval(timer)
  }, [])
  const action = async (path: string, body?: object) => {
    setBusy(true); setMessage('')
    try {
      const response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) })
      const value = await response.json(); if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '操作失败')
      setStatus(value); setMessage(value.message || '操作成功')
    } catch (e) { setMessage((e as Error).message) } finally { setBusy(false) }
  }
  const send = () => {
    const selected = versions.find(v => v.id === version)
    if (selected && window.confirm(`向 ${selected.companyName} 的 ${selected.jobName} 发送下方招呼语和已确认简历？仅处理这一个岗位。`))
      void action(`/api/resume-workflow/${version}/deliver`, { greeting })
  }
  return <div className="space-y-6">
    <PageHeader icon={<Send />} title="投递与沟通" subtitle="选择已确认的岗位专属简历，预览图片与招呼语后发送" />
    <div className="delivery-layout">
      <div className="delivery-primary">
        <Card><CardHeader><CardTitle>本次投递</CardTitle><CardDescription>一次只投递该版本对应的岗位。待确认的发送不会自动重试；持续跟进回复尚未接入。</CardDescription></CardHeader><CardContent className="space-y-4">
      <div className="flex gap-3 flex-wrap"><Button variant="outline" disabled={busy || status.running} onClick={() => action('/api/boss/browser')}>打开浏览器登录</Button><Button variant="outline" disabled={busy || !status.running} onClick={() => action('/api/boss/stop')}>停止任务</Button></div>
      <p role="status" className="text-sm">{message || status.message || '等待操作'} · {status.isLoggedIn ? 'Boss 已登录' : '未登录'}{status.challenge ? ' · 请完成安全验证' : ''}</p>
      <label htmlFor="approved-version" className="block">已确认简历</label>
      <select id="approved-version" className="ui-field w-full p-3" value={version} onChange={e => { setVersion(e.target.value); setPreviewed(false) }}><option value="">选择岗位与简历版本</option>{versions.map(v => <option value={v.id} key={v.id}>{v.companyName} · {v.jobName} · {v.id.slice(0, 6)}</option>)}</select>
      {!versions.length && <Link href="/resume" className="text-link">先去生成并确认新版简历</Link>}
      {version && <a href={`${API_BASE}/api/resume-workflow/${version}/image`} target="_blank" rel="noreferrer" className="text-link">打开投递图片，核对分页与文字</a>}
      <label htmlFor="delivery-greeting" className="block">本次打招呼内容</label><Textarea id="delivery-greeting" rows={4} value={greeting} onChange={e => setGreeting(e.target.value)} />
      <label className="select-option"><input type="checkbox" className="ui-checkbox" checked={previewed} onChange={e => setPreviewed(e.target.checked)} />已预览简历图片并核对招呼语</label>
      <Button disabled={busy || status.running || !status.isLoggedIn || status.challenge || !version || !previewed || !greeting.trim()} onClick={send}>投递该岗位并打招呼</Button>
    </CardContent></Card>
      </div>
      <section className="delivery-history" aria-label="投递记录与结果"><h2 className="mb-4 text-xl font-semibold">投递记录与结果</h2><AnalysisContent showHeader={false} view="delivery" /></section>
    </div>
  </div>
}
