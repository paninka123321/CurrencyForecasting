import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import './App.css';

// Helper component: displays the current rate (Tile)
const RateTile = ({ title, value, date, color }) => (
  <div className="rate-label">
    <h3>{title}</h3>
    <div className="value" style={{ color: color }}>
      {value ? Number(value).toFixed(4) : '---'}
    </div>
    <div className="date">{date ? new Date(date).toLocaleString() : 'Loading...'}</div>
  </div>
);

// Helper component: Metrics table
const MetricsTable = ({ metrics, currentModel }) => {
  if (!metrics || metrics.length === 0) return <p>No model metrics available</p>;
  
  return (
    <div className="metrics-section">
  <h4>Model Performance (Latest training)</h4>
      <table className="metrics-table">
        <thead>
          <tr>
          <th>Model</th>
          <th>MAE (Error)</th>
          <th>R²</th>
          </tr>
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
             )
          })}
        </tbody>
      </table>
    </div>
  );
};

export default function App() {
  // App state
  const [dataEur, setDataEur] = useState([]); // Wykres lewy
  const [dataPln, setDataPln] = useState([]); // Wykres prawy
  const [history, setHistory] = useState([]); // Wykres dolny
  const [metricsEur, setMetricsEur] = useState([]);
  const [metricsPln, setMetricsPln] = useState([]);
  
  // Data fetching function (calls backend endpoints)
  const fetchData = async () => {
    try {
      // 1. Pobieramy połączone dane historyczne + prognozy dla EUR->PLN
      const resEur = await axios.get('/api/chart-data/eurpln/'); 
      setDataEur(resEur.data.chart_data);
      setMetricsEur(resEur.data.metrics);

      // 2. Pobieramy dane dla PLN->EUR
      const resPln = await axios.get('/api/chart-data/plneur/');
      setDataPln(resPln.data.chart_data);
      setMetricsPln(resPln.data.metrics);

      // 3. Pobieramy długą historię (dolny wykres)
      const resHist = await axios.get('/api/rates/history/');
      setHistory(resHist.data);

    } catch (e) {
      console.error("Error fetching data:", e);
    }
  };

  // Run every minute
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // 60 sekund
    return () => clearInterval(interval);
  }, []);

  // Helper variables to display latest values (last point on chart)
  const lastEur = dataEur.length > 0 ? dataEur[dataEur.length - 1] : {};
  const lastPln = dataPln.length > 0 ? dataPln[dataPln.length - 1] : {};

  return (
    <div className="dashboard-container">
      <div className="header">
        <h1>Forex AI Dashboard</h1>
  <p>Live update every 1 minute | Model: {lastEur.model_name || 'Loading...'}</p>
      </div>

      <div className="top-row">
        
        {/* LEWA STRONA: EUR -> PLN (Czerwony) */}
        <div className="card">
          <RateTile 
            title="EUR -> PLN Rate" 
            value={lastEur.value} 
            date={lastEur.date} 
            color="#e74c3c" 
          />
          
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              
              <LineChart data={dataEur}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  tick={{fontSize: 10}} 
                  tickFormatter={(t) => new Date(t).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} 
                  minTickGap={30}
                />
                <YAxis domain={['auto', 'auto']} width={40} />
                <Tooltip labelFormatter={(t) => new Date(t).toLocaleString()} />
                {/* Linia Historyczna */}
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#e74c3c" 
                  strokeWidth={2} 
                  dot={false} 
                />
                {/* Opcjonalnie: Linia predykcji przerywana, jeśli dane to rozróżniają */}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <MetricsTable metrics={metricsEur} currentModel={lastEur.model_name} />
        </div>

        {/* PRAWA STRONA: PLN -> EUR (Niebieski) */}
        <div className="card">
          <RateTile 
            title="PLN -> EUR Rate" 
            value={lastPln.value} 
            date={lastPln.date} 
            color="#3498db" 
          />

          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              
              <LineChart data={dataPln}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  tick={{fontSize: 10}} 
                  tickFormatter={(t) => new Date(t).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} 
                  minTickGap={30}
                />
                <YAxis domain={['auto', 'auto']} width={40} />
                <Tooltip labelFormatter={(t) => new Date(t).toLocaleString()} />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#3498db" 
                  strokeWidth={2} 
                  dot={false} 
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <MetricsTable metrics={metricsPln} currentModel={lastPln.model_name} />
        </div>
      </div>

      {/* DOLNA SEKCJA: Historia Zielona */}
      <div className="bottom-row card">
  <h3>Full History (EUR/PLN)</h3>
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
             
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis 
                dataKey="date" 
                tick={{fontSize: 10}}
                tickFormatter={(t) => new Date(t).toLocaleDateString()}
              />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip />
              <Line 
                type="monotone" 
                dataKey="eurpln" 
                stroke="#27ae60" 
                strokeWidth={1} 
                dot={false} 
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}