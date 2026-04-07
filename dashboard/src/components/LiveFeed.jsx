import { format } from 'date-fns'
import { Shield, AlertTriangle, RefreshCw, CheckCircle, XCircle } from 'lucide-react'

const DECISION_ICONS = {
  ALLOW:   <CheckCircle size={13} color="var(--allow)" />,
  REWRITE: <RefreshCw  size={13} color="var(--rewrite)" />,
  BLOCK:   <XCircle   size={13} color="var(--block)" />,
}

function scoreColor(score) {
  if (score >= 0.7)  return 'var(--block)'
  if (score >= 0.35) return 'var(--rewrite)'
  return 'var(--allow)'
}

export default function LiveFeed({ events }) {
  const recent = events.slice(0, 100)

  return (
    <div className="page">
      <h1 className="page-title">Live Event Feed</h1>

      <div className="card" style={{padding:0,overflow:'hidden'}}>
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:12.5}}>
          <thead>
            <tr style={{background:'var(--bg-surface)',borderBottom:'1px solid var(--border)'}}>
              {['Time','Decision','Score','Trigger','Compliance','Latency','Rewritten'].map(h => (
                <th key={h} style={{
                  padding:'10px 14px',textAlign:'left',
                  color:'var(--text-muted)',fontWeight:600,fontSize:10.5,
                  letterSpacing:'0.06em',textTransform:'uppercase'
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {recent.map((e, i) => (
              <tr key={e.audit_id} style={{
                borderBottom:'1px solid var(--border)',
                background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.012)',
                transition:'background 0.1s',
              }}
              onMouseEnter={ev => ev.currentTarget.style.background='var(--bg-card-hover)'}
              onMouseLeave={ev => ev.currentTarget.style.background = i%2===0?'transparent':'rgba(255,255,255,0.012)'}
              >
                <td style={{padding:'9px 14px',fontFamily:'var(--font-mono)',color:'var(--text-muted)',fontSize:11}}>
                  {format(new Date(e.timestamp), 'HH:mm:ss')}
                </td>
                <td style={{padding:'9px 14px'}}>
                  <span className={`badge badge-${e.decision}`} style={{display:'inline-flex',alignItems:'center',gap:4}}>
                    {DECISION_ICONS[e.decision]}
                    {e.decision}
                  </span>
                </td>
                <td style={{padding:'9px 14px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:8,minWidth:100}}>
                    <div className="score-bar" style={{width:60}}>
                      <div className="score-fill" style={{
                        width:`${e.aggregate_score*100}%`,
                        background:scoreColor(e.aggregate_score)
                      }}/>
                    </div>
                    <span style={{fontFamily:'var(--font-mono)',color:scoreColor(e.aggregate_score),fontSize:11.5}}>
                      {e.aggregate_score.toFixed(3)}
                    </span>
                  </div>
                </td>
                <td style={{padding:'9px 14px',color:'var(--text-secondary)',fontSize:11}}>
                  {e.triggering_agent || <span style={{color:'var(--text-muted)'}}>—</span>}
                </td>
                <td style={{padding:'9px 14px',fontSize:10.5}}>
                  {(e.compliance_tags||[]).slice(0,2).map(t => (
                    <span key={t} style={{
                      display:'inline-block',background:'rgba(109,90,255,0.12)',
                      color:'var(--accent)',borderRadius:4,padding:'1px 6px',
                      marginRight:3,fontSize:10,
                    }}>{t.split(':')[0]}</span>
                  ))}
                  {(e.compliance_tags||[]).length > 2 &&
                    <span style={{color:'var(--text-muted)',fontSize:10}}>+{e.compliance_tags.length-2}</span>}
                </td>
                <td style={{padding:'9px 14px',fontFamily:'var(--font-mono)',color:'var(--text-muted)',fontSize:11}}>
                  {e.latency_ms?.toFixed(1)}ms
                </td>
                <td style={{padding:'9px 14px'}}>
                  {e.rewritten
                    ? <span style={{color:'var(--rewrite)',fontSize:11}}>✓</span>
                    : <span style={{color:'var(--text-muted)',fontSize:11}}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
