/* Commonwatt story data, shared by the player (commonwatt-story.html), the live 3D view
   (commonwatt-live-3d.html) and the renderer (commonwatt-bake.html). */
/* =====================================================================
   STORY: every word and number on screen lives here.
   3D points are [east, up, south] in meters. A chip's `at` is either a
   named anchor of building `b` (see BUILD.* anchors in commonwatt-kit.js)
   or a point local to that building. `bus: true` pins it to the building's grid connection.
   cam: { b, at, dist, az, el, fx, fy, drift }: orbit target (local to b),
   distance (m), azimuth from south toward east (deg), elevation (deg),
   where the target sits on the 1600x900 frame, and slow orbit (deg/s).
   ===================================================================== */
window.COMMONWATT_STORY = {
  illustrative: true,
  chapters: [
    { key:'office', nav:'Office complex', mood:'day', clock:'2:40 PM', dur:9.5,
      title:'Office complex',
      caption:'A large building with solar, a battery, and heat pumps. Its agent plans the afternoon around the evening peak.',
      cam:{ b:'office', at:[3, 6, 1], dist:86, az:38, el:24, fx:590, fy:470, drift:0.5 },
      flows:[['o_solar_bat','solar'],['o_solar_bldg','solar'],['office_out','solar']],
      chips:[
        {b:'office', at:'pv', place:'above', name:'Solar', value:'38 kW', kind:'solar'},
        {b:'office', at:'hp', place:'above', name:'Heat pumps', value:'Pre-cooling', kind:'signal'},
        {b:'office', at:'battery', place:'right', name:'Battery', value:'Charging', kind:'battery', bar:64},
        {b:'office', at:'building', place:'left', name:'Building', value:'41 kW', kind:'ink'},
        {b:'office', bus:true, place:'right', name:'Grid', value:'Sending 9 kW', kind:'solar'}
      ],
      card:{ agent:'Office complex agent', meta:'Modeled on HouseZero, Cambridge',
        title:'Storing midday sun for the evening peak',
        body:'Solar covers the building and charges the battery. Two floors pre-cool to 71°F before 5 PM, so the building can run on its battery when the neighborhood peaks.',
        offer:'−18 kW · 5–7 PM', note:'', limits:'Lab circuits never curtailed · battery reserve 20%' } },

    { key:'home', nav:'Home', mood:'day', clock:'4:15 PM', dur:9.5,
      title:'Single-family home',
      caption:'A household with rooftop solar, a battery, and a heat pump. Its agent knows the family’s comfort limits and keeps them private.',
      cam:{ at:[-26, 3, -46], dist:64, az:-26, el:31, fx:600, fy:420, drift:0.5 },
      flows:[['h7_solar_home','solar'],['h7_solar_bat','solar'],['h7_hp','solar']],
      chips:[
        {b:'home07', at:'pv', place:'above', name:'Solar', value:'3.1 kW', kind:'solar'},
        {b:'home07', at:'battery', place:'left', name:'Home battery', value:'Holding', kind:'battery', bar:88},
        {b:'home07', at:'hp', place:'above', name:'Heat pump', value:'Pre-cooling', kind:'signal'},
        {b:'home07', at:'home', place:'left', name:'Home', value:'2.6 kW', kind:'ink'},
        {b:'home07', bus:true, place:'right', name:'Grid', value:'0.0 kW', kind:'grid', idle:true},
        {b:'home03', at:'ev', place:'above', name:'EV · home_03', value:'Bidirectional', kind:'battery', bar:62}
      ],
      card:{ agent:'Home agent', meta:'Single-family home',
        title:'Pre-cooling before the peak',
        body:'The heat pump cools the house to 72°F now, on solar, so the home can coast from 5 to 7 PM. The battery holds its charge for the peak.',
        offer:'−1.2 kW · 5–7 PM', note:'Countered a request for −2.0 kW', limits:'Comfort 72–76°F · backup reserve 20%' } },

    { key:'cafe', nav:'Corner café', mood:'day', clock:'4:40 PM', dur:9.5,
      title:'Corner café',
      caption:'A small business with no solar or battery. Its flexibility is cold storage and cooling.',
      cam:{ b:'cafe', at:[2, 3.8, 2], dist:50, az:34, el:22, fx:600, fy:490, drift:0.5 },
      flows:[['cafe_in','grid'],['c_cooler','grid'],['c_hvac','grid']],
      chips:[
        {b:'cafe', at:'hvac', place:'right', name:'Rooftop HVAC', value:'Pre-cooling', kind:'signal'},
        {b:'cafe', at:'cooler', place:'right', name:'Walk-in cooler', value:'34°F', kind:'signal'},
        {b:'cafe', at:'cafe', place:'left', name:'Café', value:'Open', kind:'ink'},
        {b:'cafe', bus:true, place:'right', name:'Grid', value:'Drawing 9 kW', kind:'grid'}
      ],
      card:{ agent:'Café agent', meta:'Corner café · small business',
        title:'Pre-chilling the walk-in cooler',
        body:'The cooler drops to 34°F and the dining room to 71°F before dinner. Both coast through the peak while the café stays open.',
        offer:'−3.5 kW · 5–7 PM', note:'', limits:'Cooler never above 40°F · open 7 AM–9 PM' } },

    { key:'library', nav:'Library', mood:'day', clock:'4:55 PM', dur:9.5,
      title:'Public library',
      caption:'A public institution. Its battery is shared with the whole neighborhood.',
      cam:{ b:'library', at:[5, 5, 1], dist:90, az:34, el:24, fx:610, fy:470, drift:0.5 },
      flows:[['l_solar_bat','solar'],['l_solar_lib','solar']],
      chips:[
        {b:'library', at:'pv', place:'above', name:'Solar', value:'22 kW', kind:'solar'},
        {b:'library', at:'hvac', place:'above', name:'HVAC', value:'Pre-cooling', kind:'signal'},
        {b:'library', at:'battery', place:'right', name:'Shared battery', value:'30% held for outages', kind:'battery', bar:92},
        {b:'library', at:'library', place:'left', name:'Library', value:'Open until 8 PM', kind:'ink'},
        {b:'library', bus:true, place:'right', name:'Grid', value:'0.0 kW', kind:'grid', idle:true}
      ],
      card:{ agent:'Library agent', meta:'Public library · joining the commons',
        title:'Sharing its battery with the neighborhood',
        body:'The library hosts a battery the community shares. It always holds 30% back so the building can stay open as a cooling and warming center during an outage.',
        offer:'−25 kW · 5–7 PM', note:'', limits:'30% held for outages · reading rooms 70–75°F' } },

    { key:'network', nav:'The network', mood:'evening', clock:'4:58 PM', dur:16.5,
      title:'The network',
      caption:'5:00 PM is coming. Left alone, every building pulls power at the same time.',
      cam:{ at:[40, 4, -55], dist:420, az:14, el:28, fx:800, fy:520, drift:0.12 },
      flows:[['trunk','strain'],['bus','strain'],['bus_elm','strain'],['bus_oak','strain'],['office_in','strain'],['home03_in','strain'],['home05_in','strain'],['home07_in','strain'],['cafe_in','strain'],['library_in','strain']],
      chips:[],
      meters:{ localBefore:31, localAfter:68, peakBefore:100, peakAfter:64 },
      events:[
        {at:0.5, log:['16:58','grid','peak forecast 17:00–19:00','info']},
        {at:1.4, nodes:true, log:['17:00','commons','5 member agents online','info']},
        {at:2.4, msg:['grid','coord'], clock:'5:00 PM', log:['17:00','grid → commons','ask: reduce 50 kW, 17:00–19:00','ask']},
        {at:3.4, msg:['coord','office'], log:['17:00','commons → office','request −18 kW','req']},
        {at:4.1, msg:['office','coord'], log:['17:00','office → commons','accept −18 kW','ok']},
        {at:4.6, msg:['coord','home07'], log:['17:00','commons → home_07','request −2.0 kW','req']},
        {at:5.3, msg:['home07','coord'], log:['17:00','home_07 → commons','counter −1.2 kW (comfort limit)','counter']},
        {at:5.8, block:'home03', reason:'EV must reach 80% by 7 AM', log:['17:01','commons → home_03','request −3.0 kW (EV discharge)','req']},
        {at:6.4, log:['17:01','trust guard','blocked: home_03 EV must reach 80% by 7 AM','block']},
        {at:6.9, msg:['coord','home05'], log:['17:01','commons → home_05','request −2.3 kW','req']},
        {at:7.5, msg:['home05','coord'], log:['17:01','home_05 → commons','accept −2.3 kW','ok']},
        {at:7.9, msg:['coord','cafe'], log:['17:01','commons → café','request −3.5 kW','req']},
        {at:8.5, msg:['cafe','coord'], log:['17:01','café → commons','accept −3.5 kW','ok']},
        {at:9.1, join:'library', caption:'A library joins mid-evening. The coordinator needs no changes.', log:['17:01','library_01','joined the commons','join']},
        {at:9.8, msg:['library','coord'], log:['17:01','library_01 → commons','offer −25 kW','req']},
        {at:10.4, msg:['coord','library'], log:['17:02','commons → library_01','assign −25 kW','ok']},
        {at:11.0, msg:['coord','grid'], log:['17:02','commons → grid','committed: 50.0 kW','ok']},
        {at:11.6, relieve:true, clock:'5:30 PM', caption:'Agents negotiate. The peak flattens, and every member’s limits hold.'},
        {at:13.6, clock:'7:00 PM', log:['19:00','trust guard','receipt · home_07 · 2.4 kWh · $0.62','receipt']},
        {at:14.2, log:['19:00','trust guard','receipt · library_01 · 50 kWh · $13.00','receipt']}
      ],
      relieve:{
        flows:[['trunk','grid',0.45],['bus','grid',0.45],['bus_elm','grid',0.45],['bus_oak',null],['home03_in','grid',0.45],['cafe_in','grid',0.45],
               ['office_in',null],['home05_in',null],['home07_in',null],['library_in',null],
               ['o_bat_bldg','battery'],['h7_bat_home','battery'],['h5_bat_home','battery'],['l_bat_lib','battery']],
        smoke:0.3 } }
  ],
  /* network overlay: where each agent node floats (coord is a world point; others sit above their building) */
  network:{ coord:[22, 80, -60],
    /* screen-pixel nudges so neighboring nodes don't overlap; tethers still point at each roof */
    nudge:{ home03:[-30, 10], home05:[10, -30], home07:[20, 0], cafe:[34, 14] } }
};

