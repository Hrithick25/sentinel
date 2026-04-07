import { useMemo } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { format, subHours } from 'date-fns'

export default function ThreatHeatmap({ events }) {
  // Bucket events into hourly slots for the last 24 hours
  const hourlyData = useMemo(() => {
    const now = new Date()
    return Array.from({length: 24}, (_, i) => {
      const hour = subHours(now, 23 - i)
      const hourStr = format(hour, 'HH:00')
      const bucket = events.filter(e => {
        const t = new Date(e.timestamp)
        return t >= subHours(hour, 0.5) && t < subHours(hour, -0.5)
      })
      return {
        hour: hourStr,
        BLOCK:   bucket.filter(e => e.decision === 'BLOCK').length,
        REWRITE: bucket.filter(e => e.decision === 'REWRITE').length,
        ALLOW:   bucket.filter(e => e.decision === 'ALLOW').length,
      }
    })
  }, [events])

  // Attack taxonomy breakdown
  const taxonomy = useMemo(() => {
    const counts = {
      injection:     events.filter(e => e.triggering_agent === 'InjectionScout').length,
      pii:           events.filter(e => e.triggering_agent === 'PIISentinel').length,
      jailbreak:     events.filter(e => e.triggering_agent === 'JailbreakGuard').length,
      toxicity:      events.filter(e => e.triggering_agent === 'ToxicityScreener').length,
      hallucination: events.filter(e => e.triggering_agent === 'HallucinationProbe').length,
      multilingual:  events.filter(e => e.triggering_agent === 'MultilingualGuard').length,
      tool_abuse:    events.filter(e => e.triggering_agent === 'ToolCallSafety').length,
      brand_drift:   events.filter(e => e.triggering_agent === 'BrandGuard').length,
      token_fraud:   events.filter(e => e.triggering_agent === 'TokenAnomalyDetector').length,
      response_harm: events.filter(e => e.triggering_agent === 'ResponseSafetyLayer').length,
    }
    return Object.entries(counts).map(([k,v]) => ({name: k, count: v}))
  }, [events])

  const tooltipStyle = {
    contentStyle: {background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:8,fontSize:12},
    labelStyle: {color:'var(--text-primary)'},
    itemStyle: {color:'var(--text-secondary)'},
  }

  return (
    <div className="page">
      <h1 className="page-title">Threat Heatmap</h1>

      <div className="card">
        <div className="card-title">Decision Volume — Last 24 Hours</div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={hourlyData} margin={{top:5,right:20,left:0,bottom:5}}>
            <defs>
              <linearGradient id="gBlock"   x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"   stopColor="#ef4444" stopOpacity={0.4}/>
                <stop offset="95%"  stopColor="#ef4444" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="gRewrite" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"   stopColor="#f59e0b" stopOpacity={0.4}/>
                <stop offset="95%"  stopColor="#f59e0b" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="gAllow"   x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"   stopColor="#22c55e" stopOpacity={0.3}/>
                <stop offset="95%"  stopColor="#22c55e" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="hour" tick={{fill:'var(--text-muted)',fontSize:11}} />
            <YAxis tick={{fill:'var(--text-muted)',fontSize:11}} />
            <Tooltip {...tooltipStyle} />
            <Area type="monotone" dataKey="ALLOW"   stroke="#22c55e" fill="url(#gAllow)"   strokeWidth={2} stackId="1"/>
            <Area type="monotone" dataKey="REWRITE" stroke="#f59e0b" fill="url(#gRewrite)" strokeWidth={2} stackId="1"/>
            <Area type="monotone" dataKey="BLOCK"   stroke="#ef4444" fill="url(#gBlock)"   strokeWidth={2} stackId="1"/>
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="card-title">Attack Taxonomy</div>
        <div style={{display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:12}}>
          {taxonomy.map(({name, count}) => (
            <div key={name} style={{
              background:'var(--bg-surface)',border:'1px solid var(--border)',
              borderRadius:10,padding:'12px',textAlign:'center'
            }}>
              <div style={{fontSize:24,fontWeight:700,fontFamily:'var(--font-mono)',color:'var(--accent)'}}>{count}</div>
              <div style={{fontSize:10,color:'var(--text-muted)',marginTop:4,textTransform:'capitalize'}}>{name.replace('_', ' ')}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
