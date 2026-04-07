import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const AGENTS = [
  'InjectionScout', 'PIISentinel', 'JailbreakGuard',
  'ToxicityScreener', 'HallucinationProbe', 'ContextAnchor', 'ComplianceTagger',
  'ResponseSafetyLayer', 'MultilingualGuard', 'ToolCallSafety',
  'BrandGuard', 'TokenAnomalyDetector'
]

const COLORS = ['#6d5aff','#22c55e','#f59e0b','#ef4444','#38bdf8','#a78bfa','#fb923c', '#f472b6', '#34d399', '#fde047', '#94a3b8', '#14b8a6']

export default function AgentBreakdown({ events }) {
  const data = useMemo(() => AGENTS.map((name, i) => {
    const flagged = events.filter(e => {
      const scores = e.agent_scores || {}
      return scores[name] >= 0.6
    }).length
    const avgScore = events.length
      ? events.reduce((acc, e) => acc + ((e.agent_scores || {})[name] || 0), 0) / events.length
      : 0
    return { name: name.replace(/([A-Z])/g, ' $1').trim(), flagCount: flagged, avgScore: +avgScore.toFixed(3), color: COLORS[i] }
  }), [events])

  const triggerData = useMemo(() => AGENTS.map((name, i) => ({
    name: name.replace(/([A-Z])/g, ' $1').trim(),
    triggers: events.filter(e => e.triggering_agent === name).length,
    color: COLORS[i],
  })), [events])

  return (
    <div className="page">
      <h1 className="page-title">Agent Breakdown</h1>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16}}>
        <div className="card">
          <div className="card-title">Average Score Per Agent</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data} layout="vertical" margin={{left:10,right:20}}>
              <XAxis type="number" domain={[0,1]} tick={{fill:'var(--text-muted)',fontSize:11}} />
              <YAxis type="category" dataKey="name" tick={{fill:'var(--text-secondary)',fontSize:11}} width={110}/>
              <Tooltip
                contentStyle={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:8,fontSize:12}}
                labelStyle={{color:'var(--text-primary)'}}
                itemStyle={{color:'var(--text-secondary)'}}
              />
              <Bar dataKey="avgScore" radius={[0,4,4,0]}>
                {data.map((d,i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Trigger Count Per Agent</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={triggerData} layout="vertical" margin={{left:10,right:20}}>
              <XAxis type="number" tick={{fill:'var(--text-muted)',fontSize:11}} />
              <YAxis type="category" dataKey="name" tick={{fill:'var(--text-secondary)',fontSize:11}} width={110}/>
              <Tooltip
                contentStyle={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:8,fontSize:12}}
                labelStyle={{color:'var(--text-primary)'}}
              />
              <Bar dataKey="triggers" radius={[0,4,4,0]}>
                {triggerData.map((d,i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Agent score table */}
      <div className="card">
        <div className="card-title">Per-Agent Statistics</div>
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
          <thead>
            <tr style={{borderBottom:'1px solid var(--border)'}}>
              {['Agent','Avg Score','Flag Count','Trigger Count'].map(h => (
                <th key={h} style={{textAlign:'left',padding:'8px 12px',color:'var(--text-muted)',fontWeight:600,fontSize:11,letterSpacing:'0.05em'}}>{h.toUpperCase()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} style={{borderBottom:'1px solid var(--border)'}}>
                <td style={{padding:'10px 12px',color:'var(--text-primary)',display:'flex',alignItems:'center',gap:8}}>
                  <span style={{width:8,height:8,borderRadius:'50%',background:row.color,display:'inline-block'}}/>
                  {row.name}
                </td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>
                  <div style={{display:'flex',alignItems:'center',gap:8}}>
                    {row.avgScore.toFixed(3)}
                    <div className="score-bar" style={{flex:1}}>
                      <div className="score-fill" style={{width:`${row.avgScore*100}%`,background:row.color}}/>
                    </div>
                  </div>
                </td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>{row.flagCount}</td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>{triggerData[i].triggers}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
