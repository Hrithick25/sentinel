import { useState } from 'react'
import { Save, RefreshCw } from 'lucide-react'

const DEFAULT_POLICY = {
  injection_threshold:    0.85,
  pii_threshold:          0.70,
  toxicity_threshold:     0.60,
  hallucination_threshold:0.50,
  jailbreak_threshold:    0.75,
  response_safety_threshold:0.50,
  multilingual_threshold: 0.65,
  tool_call_threshold:    0.60,
  brand_guard_threshold:  0.50,
  token_anomaly_threshold:0.60,
  lower_threshold:        0.35,
  upper_threshold:        0.70,
  pii_action:            'redact',
  allow_rewrite:          true,
  use_case:              'general',
}

export default function ConfigPanel({ gatewayUrl, token }) {
  const [policy, setPolicy] = useState(DEFAULT_POLICY)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [tenantId, setTenantId] = useState('my-tenant')

  const setVal = (key, val) => setPolicy(prev => ({...prev, [key]: val}))

  const handleSave = async () => {
    setSaving(true)
    try {
      const resp = await fetch(`${gatewayUrl}/admin/policy/${tenantId}`, {
        method: 'PUT',
        headers: {'Content-Type':'application/json', 'Authorization':`Bearer ${token}`},
        body: JSON.stringify(policy),
      })
      if (resp.ok) { setSaved(true); setTimeout(() => setSaved(false), 2000) }
    } catch {
      alert('Could not reach gateway — running in demo mode')
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    } finally { setSaving(false) }
  }

  const sliders = [
    {key:'injection_threshold',    label:'Injection Threshold',     desc:'Score above which InjectionScout flags a request'},
    {key:'pii_threshold',          label:'PII Threshold',           desc:'Score above which PIISentinel flags a request'},
    {key:'toxicity_threshold',     label:'Toxicity Threshold',      desc:'Aggregate toxicity score triggering a flag'},
    {key:'hallucination_threshold',label:'Hallucination Threshold', desc:'Ungrounded claim fraction triggering a flag'},
    {key:'jailbreak_threshold',    label:'Jailbreak Threshold',     desc:'Multi-turn escalation score triggering a flag'},
    {key:'response_safety_threshold',label:'Response Safety',       desc:'Score above which harmful answers are blocked'},
    {key:'multilingual_threshold', label:'Multilingual Threshold',  desc:'Indic language cross-lingual jailbreak flags'},
    {key:'tool_call_threshold',    label:'Tool Call Safety',        desc:'Dangerous DB/system execution pattern blocks'},
    {key:'brand_guard_threshold',  label:'Brand Guard Threshold',   desc:'Persona drift and unauthorised promises flags'},
    {key:'token_anomaly_threshold',label:'Token Anomaly',           desc:'Prompt stuffing and token abuse rate limiting'},
    {key:'lower_threshold',        label:'ALLOW / REWRITE boundary',desc:'Aggregate score below this → ALLOW'},
    {key:'upper_threshold',        label:'REWRITE / BLOCK boundary',desc:'Aggregate score above this → BLOCK'},
  ]

  return (
    <div className="page">
      <h1 className="page-title">Safety Policy Configuration</h1>
      <p style={{color:'var(--text-secondary)',fontSize:13,marginBottom:24,marginTop:-12}}>
        Threshold changes take effect within 30 seconds (Redis TTL). No redeployment needed.
      </p>

      <div className="card" style={{marginBottom:16}}>
        <div className="card-title">Target Tenant</div>
        <input
          value={tenantId}
          onChange={e => setTenantId(e.target.value)}
          placeholder="tenant-id"
          style={{
            background:'var(--bg-surface)',border:'1px solid var(--border)',
            borderRadius:8,padding:'8px 14px',color:'var(--text-primary)',
            fontSize:13,width:280,outline:'none',fontFamily:'var(--font-mono)',
          }}
        />
        <div style={{fontSize:11,color:'var(--text-muted)',marginTop:6}}>
          Use case:
          <select
            value={policy.use_case}
            onChange={e => setVal('use_case', e.target.value)}
            style={{marginLeft:8,background:'var(--bg-surface)',border:'1px solid var(--border)',
              borderRadius:6,padding:'4px 8px',color:'var(--text-primary)',fontSize:11}}
          >
            {['general','hr','legal','code','healthcare','finance'].map(u => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Decision Thresholds</div>
        <div style={{display:'flex',flexDirection:'column',gap:20}}>
          {sliders.map(({key, label, desc}) => (
            <div key={key}>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                <div>
                  <span style={{fontSize:13,fontWeight:500,color:'var(--text-primary)'}}>{label}</span>
                  <div style={{fontSize:11,color:'var(--text-muted)',marginTop:1}}>{desc}</div>
                </div>
                <span style={{fontFamily:'var(--font-mono)',fontSize:14,fontWeight:600,color:'var(--accent)'}}>
                  {policy[key].toFixed(2)}
                </span>
              </div>
              <input
                type="range" min={0} max={1} step={0.01}
                value={policy[key]}
                onChange={e => setVal(key, parseFloat(e.target.value))}
                style={{width:'100%',accentColor:'var(--accent)'}}
              />
              <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-muted)',marginTop:2}}>
                <span>0.00 (permissive)</span><span>1.00 (strict)</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-title">PII Policy</div>
        <div style={{display:'flex',gap:12}}>
          {['redact','block','log'].map(action => (
            <button
              key={action}
              onClick={() => setVal('pii_action', action)}
              style={{
                padding:'8px 18px',borderRadius:8,border:'1px solid',
                borderColor: policy.pii_action === action ? 'var(--accent)' : 'var(--border)',
                background: policy.pii_action === action ? 'var(--accent-glow)' : 'transparent',
                color: policy.pii_action === action ? 'var(--accent)' : 'var(--text-secondary)',
                cursor:'pointer',fontSize:13,fontWeight:500,transition:'all 0.15s',
              }}
            >{action.toUpperCase()}</button>
          ))}
        </div>
        <div style={{marginTop:14,display:'flex',alignItems:'center',gap:10}}>
          <input
            type="checkbox"
            checked={policy.allow_rewrite}
            onChange={e => setVal('allow_rewrite', e.target.checked)}
            id="allow-rewrite"
            style={{accentColor:'var(--accent)',width:15,height:15}}
          />
          <label htmlFor="allow-rewrite" style={{fontSize:13,color:'var(--text-primary)',cursor:'pointer'}}>
            Allow automatic prompt rewrite (REWRITE decision)
          </label>
        </div>
        <div style={{marginTop:10,display:'flex',alignItems:'center',gap:10}}>
          <input
            type="checkbox"
            checked={policy.shadow_mode || false}
            onChange={e => setVal('shadow_mode', e.target.checked)}
            id="shadow-mode"
            style={{accentColor:'var(--accent)',width:15,height:15}}
          />
          <label htmlFor="shadow-mode" style={{fontSize:13,color:'var(--text-primary)',cursor:'pointer'}}>
            <strong style={{color:'#f59e0b'}}>Shadow Mode</strong>: Log violations but never BLOCK traffic
          </label>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        style={{
          display:'flex',alignItems:'center',gap:8,padding:'11px 24px',
          background: saved ? 'var(--allow-dim)' : 'var(--accent)',
          border:'none',borderRadius:10,color: saved ? 'var(--allow)' : '#fff',
          fontSize:14,fontWeight:600,cursor:'pointer',transition:'all 0.2s',
        }}
      >
        {saving ? <RefreshCw size={16} style={{animation:'spin 1s linear infinite'}}/> : <Save size={16}/>}
        {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Policy'}
      </button>
    </div>
  )
}
