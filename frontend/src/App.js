import React, {useEffect, useState} from 'react'
import axios from 'axios'

export default function App(){
  const [rates, setRates] = useState([])
  useEffect(()=>{
    axios.get('/api/rates/')
      .then(r=> setRates(r.data))
      .catch(e=> console.error(e))
  },[])

  return (
    <div style={{padding:20}}>
      <h2>Historical rates (EUR/PLN, USD/PLN)</h2>
      <table border="1" cellPadding="6">
        <thead>
          <tr><th>date</th><th>eurpln</th><th>usdpln</th></tr>
        </thead>
        <tbody>
          {rates.map(r=> (
            <tr key={r.date}>
              <td>{r.date}</td>
              <td>{r.eurpln}</td>
              <td>{r.usdpln}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
