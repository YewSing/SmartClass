import { useAdmin } from '../context/AdminContext'

const READINGS = [
  { key: 'temperature', label: 'Temperature', unit: '°C', warn: v => v > 26, icon: '🌡' },
  { key: 'humidity',    label: 'Humidity',    unit: '%',  warn: v => v > 70, icon: '💧' },
  { key: 'lightLevel',  label: 'Light Level', unit: ' lux', warn: () => false, icon: '☀' },
  { key: 'co2',         label: 'CO₂',         unit: ' ppm', warn: v => v > 800, icon: '💨' },
  { key: 'occupancy',   label: 'Occupancy',   unit: ' persons', warn: () => false, icon: '👥' },
]

const SENSOR_STYLE = {
  ok:      { label: '✓ OK',     cls: 'text-sc-green-dk bg-sc-green-lt' },
  fault:   { label: '✕ Fault',  cls: 'text-red-600 bg-red-50' },
  offline: { label: '○ Offline', cls: 'text-text3 bg-surface2' },
}

function OverrideControl({ label, statusKey, value, onSet }) {
  const options = [
    { val: 'auto', display: 'Auto' },
    { val: 'on',   display: 'Force On' },
    { val: 'off',  display: 'Force Off' },
  ]
  const isManual = value !== 'auto'
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[14px] font-semibold text-text1">{label}</div>
        {isManual && (
          <span className="text-[11px] font-semibold text-sc-orange bg-sc-orange-lt border border-sc-orange/30 rounded-full px-2 py-0.5">
            Manual override active
          </span>
        )}
      </div>
      <div className="text-[12px] text-text3 mb-4">
        Current mode: <span className="text-text2 font-medium capitalize">{value === 'auto' ? 'Automated (sensor-driven)' : value === 'on' ? 'Forced ON' : 'Forced OFF'}</span>
      </div>
      <div className="flex gap-2">
        {options.map(opt => (
          <button
            key={opt.val}
            onClick={() => onSet(statusKey, opt.val)}
            className={`flex-1 py-2 rounded-lg text-[12.5px] font-medium border transition-all ${
              value === opt.val
                ? 'bg-accent text-white border-accent'
                : 'bg-surface2 text-text2 border-border hover:bg-surface3 hover:text-text1'
            }`}
          >
            {opt.display}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function EnvironmentView() {
  const { state, dispatch, toast } = useAdmin()
  const env = state.env

  const setOverride = (key, value) => {
    dispatch({ type: 'ENV_OVERRIDE', payload: { [key]: value } })
    const name = key === 'acStatus' ? 'AC' : 'Lights'
    const label = value === 'auto' ? 'returned to auto' : `forced ${value.toUpperCase()}`
    toast(`${name} ${label}`, 'success')
  }

  return (
    <div className="space-y-5">
      {/* Live readings */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <span className="text-[14px] font-semibold text-text1">Live Readings</span>
          <span className="text-[12px] text-text3">Last updated {env.lastUpdated} · FR-050</span>
        </div>
        <div className="grid grid-cols-5 divide-x divide-border">
          {READINGS.map(r => {
            const raw = env[r.key]
            const isWarn = r.warn(raw)
            return (
              <div key={r.key} className={`px-5 py-5 ${isWarn ? 'bg-sc-orange-lt/40' : ''}`}>
                <div className="text-[18px] mb-1">{r.icon}</div>
                <div className={`text-[22px] font-bold tracking-tight ${isWarn ? 'text-sc-orange' : 'text-text1'}`}>
                  {raw}{r.unit}
                </div>
                <div className="text-[12px] text-text3 mt-0.5">{r.label}</div>
                {isWarn && (
                  <div className="text-[10px] font-semibold text-sc-orange mt-1 uppercase tracking-wide">Above threshold</div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Override controls */}
      <div className="grid grid-cols-2 gap-3.5">
        <OverrideControl
          label="Air Conditioning"
          statusKey="acStatus"
          value={env.acStatus}
          onSet={setOverride}
        />
        <OverrideControl
          label="Lighting"
          statusKey="lightStatus"
          value={env.lightStatus}
          onSet={setOverride}
        />
      </div>

      {/* Sensor health */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <span className="text-[14px] font-semibold text-text1">Sensor Health</span>
          <span className="text-[12px] text-text3 ml-3">FR-051 — alerts generated on fault detection</span>
        </div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface2">
              {['Sensor', 'Status', 'Note'].map(h => (
                <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(env.sensors).map(([name, status]) => {
              const s = SENSOR_STYLE[status] ?? SENSOR_STYLE.offline
              return (
                <tr key={name} className="hover:bg-gray-50">
                  <td className="px-5 py-3 border-b border-border text-[13.5px] text-text1">{name}</td>
                  <td className="px-5 py-3 border-b border-border">
                    <span className={`inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded-[5px] ${s.cls}`}>
                      {s.label}
                    </span>
                  </td>
                  <td className="px-5 py-3 border-b border-border text-[12px] text-text3">
                    {status === 'fault'   ? 'Sensor not responding — check hardware connection' :
                     status === 'offline' ? 'No data received' : 'Operating normally'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
