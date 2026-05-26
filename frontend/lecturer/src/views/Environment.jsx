import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { SENSORS } from '../data/mockData'

export default function Environment() {
  const { openModal } = useLecturer()
  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Environment Control"
        sub="DK 6, BLI Building · Live sensors"
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div className="status-dot green"></div>
            <span style={{ fontSize: 11, color: 'var(--green-dk)', fontWeight: 700 }}>Live</span>
          </div>
        }
      />
      <div className="scroll-body">
        <div className="alert-banner">
          <div className="ico"><i className="fa fa-exclamation-triangle"></i></div>
          <div className="msg">CO₂ level elevated at 1240 ppm — ventilation recommended. Threshold: 1000 ppm.</div>
        </div>
        <div className="section-header" style={{ paddingTop: 4 }}>
          <span className="section-title">Sensor Readings</span>
          <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>Updated 10:14 AM</span>
        </div>
        <div className="sensor-grid">
          <div className="sensor-card">
            <div className="s-icon" style={{ color: '#E03A3A' }}><i className="fa fa-thermometer-half"></i></div>
            <div className="s-name">Temperature</div>
            <div><span className="s-val">26.4</span><span className="s-unit"> °C</span></div>
            <div style={{ marginTop: 8 }}><span className="badge green">Normal</span></div>
          </div>
          <div className="sensor-card">
            <div className="s-icon" style={{ color: '#1B6EF3' }}><i className="fa fa-tint"></i></div>
            <div className="s-name">Humidity</div>
            <div><span className="s-val">61</span><span className="s-unit"> %</span></div>
            <div style={{ marginTop: 8 }}><span className="badge green">Normal</span></div>
          </div>
          <div className="sensor-card warn">
            <div className="s-icon" style={{ color: '#D4960A' }}><i className="fa fa-wind"></i></div>
            <div className="s-name">CO₂ Level</div>
            <div><span className="s-val">1240</span><span className="s-unit"> ppm</span></div>
            <div style={{ marginTop: 8 }}><span className="badge yellow">Elevated</span></div>
          </div>
          <div className="sensor-card">
            <div className="s-icon" style={{ color: '#E87722' }}><i className="fa fa-sun"></i></div>
            <div className="s-name">Light Level</div>
            <div><span className="s-val">420</span><span className="s-unit"> lux</span></div>
            <div style={{ marginTop: 8 }}><span className="badge green">Normal</span></div>
          </div>
          <div className="sensor-card" style={{ gridColumn: 'span 2' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div><div className="s-icon" style={{ color: 'var(--gray-500)' }}><i className="fa fa-users"></i></div></div>
              <div>
                <div className="s-name">Occupancy</div>
                <div><span className="s-val">23</span><span className="s-unit"> / 30 seats</span></div>
              </div>
              <div style={{ marginLeft: 'auto' }}><span className="badge green">Normal</span></div>
            </div>
          </div>
        </div>
        <div className="section-header"><span className="section-title">Actuation Control</span></div>
        <div className="actuation-card">
          <div className="actuation-row">
            <div className="act-icon lights"><i className="fa fa-lightbulb" style={{ color: 'var(--yellow)', fontSize: 20 }}></i></div>
            <div className="act-info">
              <div className="name">Lights</div>
              <div className="status">Auto Mode · <span style={{ color: 'var(--green)', fontWeight: 700 }}>ON</span></div>
            </div>
            <span className="badge green" style={{ marginRight: 8 }}>Auto</span>
            <button className="btn btn-sm btn-outline" onClick={() => openModal('override-lights')}>Override</button>
          </div>
        </div>
        <div className="actuation-card">
          <div className="actuation-row">
            <div className="act-icon ac"><i className="fa fa-snowflake" style={{ color: 'var(--blue)', fontSize: 20 }}></i></div>
            <div className="act-info">
              <div className="name">Air Conditioning</div>
              <div className="status">Auto Mode · <span style={{ color: 'var(--green)', fontWeight: 700 }}>ON</span> · Set 23°C</div>
            </div>
            <span className="badge green" style={{ marginRight: 8 }}>Auto</span>
            <button className="btn btn-sm btn-outline" onClick={() => openModal('override-ac')}>Override</button>
          </div>
        </div>
        <div style={{ height: 20 }}></div>
      </div>
    </>
  )
}
