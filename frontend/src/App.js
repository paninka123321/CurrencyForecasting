import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import './App.css';

// --- COMPONENTS ---
const RateTile = ({ title, value, date, color }) => (
  <div className="rate-label">
    <h3>{title}</h3>
    <div className="value" style={{ color: color }}>
      {value ? Number(value).toFixed(4) : '---'}
    </div>
    <div className="date">{date ? new Date(date).toLocaleString() : 'Loading...'}</div>
  </div>
);

const MetricsTable = ({ metrics, currentModel }) => {
  if (!metrics || metrics.length === 0) return <p>No model metrics available</p>;
  return (
    <div className="metrics-section">
      <h4>Model Performance (Latest training)</h4>
      <table className="metrics-table">
        <thead>
          <tr><th>Model</th><th>MAE (Error)</th><th>R²</th></tr>
        </thead>
        <tbody>
          {metrics.map((m, idx) => {
            const isWinner = m.model_name === currentModel;
            return (
              <tr key={idx} className={isWinner ? 'winner' : ''}>
                <td>{m.model_name} {isWinner && '⭐'}</td>
                <td>{Number(m.mae).toFixed(5)}</td>
                <td>{Number(m.r2).toFixed(4)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const AdvancedPlotCard = ({ title, plotBase64, loading }) => (
  <div className="card advanced-card">
    <h3>{title}</h3>
    <div className="plot-display-area" style={{ 
      minHeight: '300px', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      backgroundColor: '#1a1a1a',
      borderRadius: '8px',
      overflow: 'hidden',
      border: '1px solid #333'
    }}>
      {loading ? (
        <div className="ai-loader">
          <div className="spinner"></div>
          <p>AI Engine calculating...</p>
        </div>
      ) : plotBase64 ? (
        <img 
          src={`data:image/png;base64,${plotBase64}`} 
          alt={title} 
          style={{ width: '100%', height: 'auto', display: 'block' }} 
        />
      ) : (
        <p style={{ color: '#666' }}>No plot data available.</p>
      )}
    </div>
  </div>
);

// --- MAIN APP ---
export default function App() {
  const [activeTab, setActiveTab] = useState('linear');
  
  // --- LIVE CLOCK STATE ---
  const [currentTime, setCurrentTime] = useState(new Date());

  // Data States
  const [dataEur, setDataEur] = useState([]);
  const [dataPln, setDataPln] = useState([]);
  const [history, setHistory] = useState([]);
  const [metricsEur, setMetricsEur] = useState([]);
  const [metricsPln, setMetricsPln] = useState([]);
  const [advPlots, setAdvPlots] = useState({ eur: null, usd: null });
  const [advLoading, setAdvLoading] = useState(false);

  // --- EFFECT FOR LIVE CLOCK ---
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer); // Cleanup on unmount
  }, []);

  const fetchData = async () => {
    try {
      const resEur = await axios.get('/api/chart-data/eurpln/'); 
      setDataEur(resEur.data.chart_data);
      setMetricsEur(resEur.data.metrics);

      const resPln = await axios.get('/api/chart-data/plneur/');
      setDataPln(resPln.data.chart_data);
      setMetricsPln(resPln.data.metrics);

      const resHist = await axios.get('/api/rates/history/');
      setHistory(resHist.data);
    } catch (e) {
      console.error("Error fetching standard data:", e);
    }
  };

  const fetchAdvancedPlots = async () => {
    setAdvLoading(true);
    try {
      const res = await axios.get('/api/advanced-prediction/');
      setAdvPlots({
        eur: res.data.eurpln,
        usd: res.data.usdpln
      });
    } catch (e) {
      console.error("Error fetching advanced plots:", e);
    }
    setAdvLoading(false);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'advanced' && (!advPlots.eur || !advPlots.usd)) {
      fetchAdvancedPlots();
    }
  }, [activeTab]);

  const lastEur = dataEur.length > 0 ? dataEur[dataEur.length - 1] : {};

  return (
    <div className="dashboard-container">
      <div className="header">
        <div className="header-main">
          <div>
            <h1>Forex AI Dashboard</h1>
            <p>Live update every 1 minute | Model: {lastEur.model_name || 'Loading...'}</p>
          </div>
          
          {/* --- LIVE CLOCK DISPLAY --- */}
          <div className="live-clock-container">
            <div className="clock-label">WARSAW TIME</div>
            <div className="clock-time">
              {currentTime.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
            <div className="clock-date">
              {currentTime.toLocaleDateString('pl-PL', { day: '2-digit', month: 'long', year: 'numeric' })}
            </div>
          </div>
        </div>
        
        <div className="tab-navigation">
          <button 
            className={activeTab === 'linear' ? 'tab-btn active' : 'tab-btn'} 
            onClick={() => setActiveTab('linear')}
          >
            Next 1 minute prediction
          </button>
          <button 
            className={activeTab === 'advanced' ? 'tab-btn active' : 'tab-btn'} 
            onClick={() => setActiveTab('advanced')}
          >
            Next 4 hours prediction
          </button>
        </div>
      </div>

      {activeTab === 'linear' ? (
        <div className="tab-content fade-in">
          <div className="top-row">
            <div className="card">
              <RateTile title="EUR -> PLN Rate" value={lastEur.value} date={lastEur.date} color="#e74c3c" />
              <div style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataEur}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#333" />
                    <XAxis 
                      dataKey="date" 
                      tick={{fontSize: 10}} 
                      tickFormatter={(t) => new Date(t).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} 
                      minTickGap={30}
                    />
                    <YAxis domain={['auto', 'auto']} width={40} />
                    <Tooltip labelFormatter={(t) => new Date(t).toLocaleString()} />
                    <Line type="monotone" dataKey="value" stroke="#e74c3c" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <MetricsTable metrics={metricsEur} currentModel={lastEur.model_name} />
            </div>

            <div className="card">
              <RateTile title="PLN -> EUR Rate" value={dataPln.length > 0 ? dataPln[dataPln.length-1].value : 0} date={dataPln.length > 0 ? dataPln[dataPln.length-1].date : null} color="#3498db" />
              <div style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataPln}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#333" />
                    <XAxis 
                      dataKey="date" 
                      tick={{fontSize: 10}} 
                      tickFormatter={(t) => new Date(t).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} 
                      minTickGap={30}
                    />
                    <YAxis domain={['auto', 'auto']} width={40} />
                    <Tooltip labelFormatter={(t) => new Date(t).toLocaleString()} />
                    <Line type="monotone" dataKey="value" stroke="#3498db" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <MetricsTable metrics={metricsPln} currentModel={dataPln.length > 0 ? dataPln[dataPln.length-1].model_name : ''} />
            </div>
          </div>

          <div className="bottom-row card">
            <h3>Full History (EUR/PLN)</h3>
            <div style={{ height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#333" />
                  <XAxis dataKey="date" tick={{fontSize: 10}} tickFormatter={(t) => new Date(t).toLocaleDateString()} />
                  <YAxis domain={['auto', 'auto']} />
                  <Tooltip />
                  <Line type="monotone" dataKey="eurpln" stroke="#27ae60" strokeWidth={1} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="tab-content fade-in">
          <div className="advanced-container">
            <div style={{ marginBottom: '15px', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="tab-btn" onClick={fetchAdvancedPlots} disabled={advLoading}>
                {advLoading ? 'Processing...' : '🔄 Refresh AI Analysis'}
              </button>
            </div>
            
            <div className="advanced-grid">
              <AdvancedPlotCard 
                title="EUR/PLN" 
                plotBase64={advPlots.eur} 
                loading={advLoading} 
              />
              <AdvancedPlotCard 
                title="USD/PLN" 
                plotBase64={advPlots.usd} 
                loading={advLoading} 
              />
            </div>
            
            <div className="card" style={{ marginTop: '20px' }}>
              <h3>Model Logic Details</h3>
              <p style={{ color: '#aaa', fontSize: '0.9rem' }}>
                Server-side generation using <strong>XGBoost</strong> and <strong>Ridge Regression</strong>. 
                Lookback=24h | Forecast=4h. Shaded areas represent prediction variance.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}