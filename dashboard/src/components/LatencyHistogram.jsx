import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts'

function percentile(sorted, p) {
  const idx = Math.floor(p * sorted.length)
  return sorted[Math.min(idx, sorted.length - 1)] || 0
}

export default function LatencyHistogram({ events }) {
  const latencies = useMemo(() =>
    events.map(e => e.latency_ms).filter(Boolean).sort((a, b) => a - b),
    [events]
  )

  const p50 = percentile(latencies, 0.50).toFixed(1)
  const p95 = percentile(latencies, 0.95).toFixed(1)
  const p99 = percentile(latencies, 0.99).toFixed(1)
  const avg = latencies.length ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(1) : '—'

  // Bucket into 10ms bins for histogram
  const histData = useMemo(() => {
    const bins = {}
    latencies.forEach(ms => {
      const bucket = Math.floor(ms / 10) * 10
      bins[bucket] = (bins[bucket] || 0) + 1
    })
    return Object.entries(bins).sort(([a],[b]) => +a - +b).map(([ms, count]) => ({
      ms: `${ms}ms`,
      count,
    }))
  }, [latencies])

  // Per-decision latency distribution
  const byDecision = useMemo(() => {
    const groups = {ALLOW:[], REWRITE:[], BLOCK:[]}
    events.forEach(e => { if (groups[e.decision]) groups[e.decision].push(e.latency_ms) })
    return Object.entries(groups).map(([decision, lats]) => {
      const sorted = [...lats].sort((a,b)=>a-b)
      return {
        decision,
        avg: sorted.length ? (sorted.reduce((a,b)=>a+b,0)/sorted.length).toFixed(1) : '—',
        p99: percentile(sorted, 0.99).toFixed(1),
        count: sorted.length,
      }
    })
  }, [events])

  const tooltipStyle = {
    contentStyle:{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:8,fontSize:12},
    labelStyle:{color:'var(--text-primary)'},
    itemStyle:{color:'var(--text-secondary)'},
  }

  return (
    <div className="page">
      <h1 className="page-title">Latency Analysis</h1>

      {/* Percentile cards */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:16}}>
        {[
          {label:'Avg', value:`${avg}ms`, color:'var(--accent)'},
          {label:'P50', value:`${p50}ms`, color:'var(--allow)'},
          {label:'P95', value:`${p95}ms`, color:'var(--rewrite)'},
          {label:'P99', value:`${p99}ms`, color:'var(--block)'},
        ].map(({label,value,color}) => (
          <div key={label} className="card" style={{textAlign:'center',padding:'20px 16px'}}>
            <div style={{fontSize:11,color:'var(--text-muted)',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:8}}>{label}</div>
            <div style={{fontSize:26,fontWeight:700,fontFamily:'var(--font-mono)',color}}>{value}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Latency Distribution (10ms bins)</div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={histData} margin={{top:5,right:20,left:0,bottom:5}}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="ms" tick={{fill:'var(--text-muted)',fontSize:10}} interval={2}/>
            <YAxis tick={{fill:'var(--text-muted)',fontSize:11}}/>
            <Tooltip {...tooltipStyle}/>
            <ReferenceLine x={`${Math.floor(+p99/10)*10}ms`} stroke="var(--block)" strokeDasharray="4 2" label={{value:'P99',fill:'var(--block)',fontSize:10}}/>
            <Bar dataKey="count" fill="var(--accent)" opacity={0.8} radius={[3,3,0,0]}/>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="card-title">Avg Latency by Decision</div>
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
          <thead>
            <tr style={{borderBottom:'1px solid var(--border)'}}>
              {['Decision','Count','Avg','P99'].map(h => (
                <th key={h} style={{textAlign:'left',padding:'8px 12px',color:'var(--text-muted)',fontSize:11,fontWeight:600}}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {byDecision.map(row => (
              <tr key={row.decision} style={{borderBottom:'1px solid var(--border)'}}>
                <td style={{padding:'10px 12px'}}>
                  <span className={`badge badge-${row.decision}`}>{row.decision}</span>
                </td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>{row.count}</td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>{row.avg}ms</td>
                <td style={{padding:'10px 12px',fontFamily:'var(--font-mono)',color:'var(--text-secondary)'}}>{row.p99}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
