'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowRight, Check, CircleDot, FileText, Inbox, ListFilter, Send, Settings2, Sparkles } from 'lucide-react'
import { API_BASE } from '@/lib/api'

type Stats = { kpi?: { total?: number; delivered?: number; pending?: number; filtered?: number; failed?: number } }
type Status = { message?: string; browserOpen?: boolean; isLoggedIn?: boolean; running?: boolean }

const steps = [
  { label: '档案与事实', detail: '确认你的经历、期望与限制', icon: FileText, href: '/boss' },
  { label: '岗位', detail: '从 Boss 采集岗位', icon: Inbox, href: '/boss' },
  { label: '匹配', detail: '按条件和黑名单筛选', icon: ListFilter, href: '/boss/analysis' },
  { label: '材料', detail: '准备招呼与图片简历', icon: Sparkles, href: '/ai-config' },
  { label: '投递', detail: '逐条确认后发送', icon: Send, href: '/boss' },
]

export default function Home() {
  const [stats, setStats] = useState<Stats>({})
  const [status, setStatus] = useState<Status>({})

  useEffect(() => {
    const load = async () => {
      try {
        const [statsResponse, statusResponse] = await Promise.all([
          fetch(`${API_BASE}/api/boss/stats`),
          fetch(`${API_BASE}/api/boss/status`),
        ])
        if (statsResponse.ok) setStats(await statsResponse.json())
        if (statusResponse.ok) setStatus(await statusResponse.json())
      } catch { /* 首页保持可用，侧栏会显示后端连接状态 */ }
    }
    void load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [])

  const kpi = stats.kpi || {}
  const cards = [
    { label: '档案与事实', value: kpi.total || 0, note: '已确认岗位记录', tone: 'done' },
    { label: '岗位', value: kpi.total || 0, note: '其中 Boss 采集', tone: 'done' },
    { label: '匹配', value: (kpi.total || 0) - (kpi.filtered || 0), note: '次排序记录', tone: 'done' },
    { label: '材料', value: 0, note: '份已批准 · 草稿 0 份', tone: 'current' },
    { label: '投递', value: kpi.delivered || 0, note: '个岗位已登记投递', tone: 'idle' },
  ]

  return (
    <div className="desk-home">
      <header className="desk-header">
        <div>
          <p className="kicker">BOSS 直聘 · 本机工作台</p>
          <h1>工作台</h1>
          <p className="lede">从确认事实到投递记录，每一步都在本机完成。简历里的每一句话，都能追到你确认过的一条事实。</p>
        </div>
        <Link className="quiet-action" href="/boss"><Settings2 size={16} /> 管理 Boss 配置</Link>
      </header>

      <section className="step-strip" aria-label="求职流程">
        {steps.map((step, index) => {
          const Icon = step.icon
          const complete = index < 3 && (kpi.total || 0) > 0
          const active = index === 3
          return <Link href={step.href} className={`step-cell ${active ? 'step-current' : ''}`} key={step.label}>
            <div className="step-top">第 {index + 1} 步 {complete && <Check size={13} />}</div>
            <div className="step-title"><Icon size={16} />{step.label}</div>
            <strong>{cards[index].value}</strong>
            <span>{step.detail}</span>
          </Link>
        })}
      </section>

      <div className="desk-grid">
        <section>
          <h2>下一步</h2>
          <article className="next-card">
            <div className="next-icon"><CircleDot size={22} /></div>
            <div>
              <h3>先打开浏览器，再采集岗位</h3>
              <p>在 Boss 直聘中完成登录。确认搜索条件后，采集只会记录岗位，不会发送任何消息。</p>
              <Link href="/boss" className="text-link">去 Boss 工作台 <ArrowRight size={15} /></Link>
            </div>
          </article>
        </section>

        <section className="status-panel">
          <h2>运行状态</h2>
          <dl>
            <div><dt>大模型</dt><dd>由你配置，自动抽取与草拟</dd></div>
            <div><dt>岗位来源</dt><dd>Boss 直聘</dd></div>
            <div><dt>最近采集</dt><dd>{kpi.total ? `${kpi.total} 条记录` : '还没有采集记录'}</dd></div>
            <div><dt>浏览器</dt><dd className={status.browserOpen ? 'live' : ''}>{status.browserOpen ? (status.isLoggedIn ? '已登录' : '已打开，等待登录') : '未打开'}</dd></div>
          </dl>
          <p className="status-note">{status.message || '系统只在本机运行，不会向招聘平台发送未确认的内容。'}</p>
        </section>
      </div>
    </div>
  )
}
