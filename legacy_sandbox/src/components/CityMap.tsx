import { useState } from 'react';
import type { MouseEvent } from 'react';
import type { Patient, Provider, Point } from '../data/scenario';
import { scoreAccess } from '../model/accessibility';
import { MapPin, Plus } from 'lucide-react';

type Props = { patient: Patient; providers: Provider[]; selectedId: string | null; onSelect: (id: string) => void; placing: boolean; onPlace: (point: Point) => void };
export function CityMap({ patient, providers, selectedId, onSelect, placing, onPlace }: Props) {
 const [hovered, setHovered] = useState<string|null>(null);
 function onClick(e: MouseEvent<SVGSVGElement>) {
   if (!placing) return;
   const rect = e.currentTarget.getBoundingClientRect();
   const p = {x: Math.max(5,Math.min(95,(e.clientX-rect.left)/rect.width*100)), y:Math.max(5,Math.min(95,(e.clientY-rect.top)/rect.height*100))};
   onPlace(p);
 }
 const visible = providers.map(p=>({p,r:scoreAccess(patient,p)}));
 return <div className={`map-frame ${placing?'is-placing':''}`}>
   <div className="map-top-left"><span className="map-live-dot"/> SYNTHETIC PHILADELPHIA <span className="muted">· Schematic geography</span></div>
   {placing && <div className="placement-hint"><Plus size={16}/> Click a location to place a new clinic</div>}
   <svg className="city-map" viewBox="0 0 1000 680" preserveAspectRatio="none" onClick={onClick} role="img" aria-label="Schematic Philadelphia map showing patients, provider markers and weighted links">
     <defs><pattern id="minorGrid" width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke="#e5ebee" strokeWidth="1"/></pattern><filter id="softShadow"><feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity=".17"/></filter></defs>
     <rect width="1000" height="680" fill="#f2f5f2"/><rect width="1000" height="680" fill="url(#minorGrid)"/>
     <path d="M-20 123L145 75 270 110 330 155 390 280 412 460 321 650 100 700 -20 700Z" fill="#e5efe6" opacity=".8"/>
     <path d="M700-20L1010-20 1010 350 912 383 856 306 765 217Z" fill="#e5efe6"/>
     <path d="M395 -30 C390 93 455 145 455 260 S445 435 507 555 S569 640 580 715" fill="none" stroke="#c8e2eb" strokeWidth="55"/>
     <path d="M395 -30 C390 93 455 145 455 260 S445 435 507 555 S569 640 580 715" fill="none" stroke="#e7f5f8" strokeWidth="37"/>
     <g fill="none" stroke="#fff" strokeWidth="11" opacity=".95"><path d="M0 340L1000 340M0 480L1000 480M0 210L1000 210M150 0L320 680M600 0L600 680M740 0L740 680M0 590L1000 590"/></g>
     <g fill="none" stroke="#d6ddda" strokeWidth="1.8"><path d="M0 340L1000 340M0 480L1000 480M0 210L1000 210M150 0L320 680M600 0L600 680M740 0L740 680M0 590L1000 590"/></g>
     <g className="map-labels" fill="#92a29c" fontSize="16" fontWeight="650" letterSpacing="2"><text x="125" y="175">WEST PHILLY</text><text x="540" y="295">CENTER CITY</text><text x="570" y="95">NORTH PHILLY</text><text x="584" y="628">SOUTH PHILLY</text><text x="785" y="148">NORTHEAST</text><text x="224" y="600">UNIVERSITY CITY</text></g>
     <text x="423" y="555" transform="rotate(-72 423 555)" fill="#7baabd" fontSize="15" letterSpacing="2">SCHUYLKILL RIVER</text>
     {visible.map(({p,r})=><line key={'line'+p.id} x1={patient.location.x*10} y1={patient.location.y*6.8} x2={p.location.x*10} y2={p.location.y*6.8} stroke={r.score===0?'#e28e86':r.score>=65?'#23977a':'#d6a144'} strokeWidth={p.id===selectedId?4.4:2.3} strokeDasharray={r.score===0?'7 9':undefined} opacity={p.id===selectedId ? .95 : .54} style={{pointerEvents:'none'}} />)}
     {visible.map(({p,r})=><g key={p.id} className="provider-marker" role="button" aria-label={`${p.name}: accessibility ${r.score}`} onClick={e=>{e.stopPropagation();onSelect(p.id)}} onMouseEnter={()=>setHovered(p.id)} onMouseLeave={()=>setHovered(null)} style={{cursor:'pointer'}}>
        {selectedId===p.id && <circle cx={p.location.x*10} cy={p.location.y*6.8} r="29" fill="none" stroke="#233d51" strokeWidth="3" opacity=".65"/>}
        <circle cx={p.location.x*10} cy={p.location.y*6.8} r="21" fill={r.score===0?'#d67972':r.score>=65?'#248c76':'#d4a04d'} stroke="#fff" strokeWidth="3" filter="url(#softShadow)"/>
        <text x={p.location.x*10} y={p.location.y*6.8+5} textAnchor="middle" fontSize="14" fontWeight="750" fill="#fff">{Math.round(r.score)}</text>
        {(hovered===p.id || selectedId===p.id) && <g transform={`translate(${p.location.x*10},${p.location.y*6.8-32})`}><rect x="-92" y="-27" width="184" height="23" rx="8" fill="#263e48"/><text x="0" y="-11" fill="white" fontSize="12" textAnchor="middle" fontWeight="600">{p.name}</text></g>}
      </g>)}
     <g style={{pointerEvents:'none'}}><circle cx={patient.location.x*10} cy={patient.location.y*6.8} r="32" fill="#537dd2" opacity=".15"/><circle cx={patient.location.x*10} cy={patient.location.y*6.8} r="21" fill="#4269bd" stroke="#fff" strokeWidth="4" filter="url(#softShadow)"/><text x={patient.location.x*10} y={patient.location.y*6.8+5} fill="#fff" textAnchor="middle" fontSize="15" fontWeight="800">{patient.name.slice(-1)}</text></g>
   </svg>
   <div className="map-legend"><span><i className="legend-dot patient"/> Patient</span><span><i className="legend-dot strong"/> High score</span><span><i className="legend-dot medium"/> Moderate</span><span><i className="legend-dot blocked"/> Blocked</span></div>
   <div className="map-scale"><MapPin size={12}/> Not to geographic scale</div>
 </div>;
}
