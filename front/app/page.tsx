'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowRight, Check, CircleDot, FileText, Inbox, ListFilter, Send, Settings2, Sparkles } from 'lucide-react'
import { API_BASE } from '@/lib/api'

type Stats = { kpi?: { total?: number; delivered?: number; pending?: number; filtered?: number; failed?: number } }
type Status = { message?: string; browserOpen?: boolean; isLoggedIn?: boolean; running?: boolean }

const steps = [
  { label: '采集岗位 JD', detail: '浏览器采集职位描述与要求', icon: Inbox, href: '/boss' },
  { label: '优化简历', detail: '原简历 + JD，Builder 后可选润色', icon: Sparkles, href: '/resume' },
  { label: '投递与沟通', detail: '确认专属简历与招呼语后发送', icon: Send, href: '/delivery' },
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
    { value: kpi.total || 0 },
    { value: 'Builder → 润色' },
    { value: kpi.delivered || 0 },
  ]

  return (
    <div className="desk-home">
      <header className="desk-header">
        <div>
          <p className="kicker">BOSS 直聘 · 本机工作台</p>
          <h1>工作台</h1>
          <p className="lede">先采集 JD，再为目标岗位生成简历，核对后投递。浏览器与文件在本机运行，简历优化调用你配置的 AI 服务。</p>
        </div>
        <Link className="quiet-action" href="/boss"><Settings2 size={16} /> 管理 Boss 配置</Link>
      </header>

      <section className="step-strip" aria-label="求职流程">
        {steps.map((step, index) => {
          const Icon = step.icon
          const complete = index === 0 && (kpi.total || 0) > 0
          const active = index === ((kpi.total || 0) > 0 ? 1 : 0)
          return <Link href={step.href} className={`step-cell ${active ? 'step-current' : ''}`} key={step.label}>
            <div className="step-top">第 {index + 1} 步 {complete && <Check size={13} />}</div>
            <div className="step-title"><Icon size={16} />{step.label}</div>
            <strong style={index === 1 ? { fontSize: 18 } : undefined}>{cards[index].value}</strong>
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
              <h3>{kpi.total ? "选择目标岗位，生成专属简历" : "先打开浏览器，再采集岗位"}</h3>
              <p>{kpi.total ? "上传原简历，核对提取文字；Resume Builder 对齐 JD，Humanizer-zh 按需优化表达。" : "在 Boss 完成登录，保存搜索条件后采集 JD。采集不会发送消息。"}</p>
              <Link href={kpi.total ? "/resume" : "/boss"} className="text-link">{kpi.total ? "去优化简历" : "去采集岗位"} <ArrowRight size={15} /></Link>
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
