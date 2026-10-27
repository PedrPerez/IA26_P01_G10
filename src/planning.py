"""Pesquisa por ondas diárias, com lotes de janelas compatíveis.
O espaço restrito é explicado nos notebooks; não representa todo o VRP.
"""
from dataclasses import dataclass
from itertools import permutations
import pandas as pd
from .model import Route, Stop

@dataclass(frozen=True)
class Batch:
    action: str
    location: int
    items: tuple
    start: object
    end: object

class Planner:
    def __init__(self, problem):
        self.problem = problem
        self.vehicles = tuple(problem.vehicles.values())
        if len(self.vehicles) != 2 or len(problem.warehouses) != 1:
            raise ValueError('Esta formulação usa dois veículos e um armazém.')
        self.depot = self.vehicles[0].depot
        groups = {}
        for r in problem.requests.values():
            for action, loc, start, end in [('pickup',r.pickup,r.available_start,r.available_end),
                                            ('deliver',r.delivery,r.delivery_start,r.delivery_end)]:
                slot = 0 if action=='pickup' else (1 if r.available_start.normalize()<start.normalize() else 2)
                key = (start.normalize(), slot, action, loc)
                groups.setdefault(key, []).append((r.id,start,end))
        waves = {}
        for (day, slot, action, loc), entries in groups.items():
            start, end = max(x[1] for x in entries), min(x[2] for x in entries)
            if start > end:
                raise ValueError('Lote sem interseção de janelas: dividir antes de pesquisar.')
            waves.setdefault((day,slot),[]).append(
                Batch(action,loc,tuple(x[0] for x in entries),start,end))
        self.waves = [tuple(v) for k,v in sorted(waves.items())]
        self.options = [self._options(w) for w in self.waves]
        if any(not options for options in self.options):
            raise ValueError('Nenhuma distribuição respeita a capacidade: dividir os lotes.')
        self.bounds = []
        for wave, options in zip(self.waves,self.options):
            radial = max(2*problem.travel(self.depot,b.location)[0] for b in wave)
            exact = min(self.option_cost(wave,o) for o in options)
            self.bounds.append((min(radial,exact),exact))

    def _options(self,wave):
        n=len(wave); out=[]
        for order in permutations(range(n)):
            for cut in range(n+1):
                option=(order[:cut],order[cut:])
                if all(sum(self.problem.requests[i].weight for k in seq for i in wave[k].items)
                       <= self.vehicles[v].capacity+1e-9 for v,seq in enumerate(option)):
                    out.append(option)
        return out

    def option_cost(self,wave,option):
        total=0
        for seq in option:
            loc=self.depot
            for k in seq:
                total+=self.problem.travel(loc,wave[k].location)[0];loc=wave[k].location
            total+=self.problem.travel(loc,self.depot)[0]
        return total

    def initial(self):
        return (tuple(Route(v.id,self.problem.start,[]) for v in self.vehicles),
                tuple(self.problem.start for v in self.vehicles),{})

    def extend(self,state,depth,option):
        routes,times,stock=state
        routes=[Route(r.vehicle_id,r.start,list(r.stops)) for r in routes]
        times=list(times);stock=dict(stock);wave=self.waves[depth];p=self.problem
        for v,seq in enumerate(option):
            if not seq: continue
            batches=[wave[k] for k in seq];items=tuple(i for b in batches for i in b.items)
            t=times[v];loc=self.depot;stops=[]
            if batches[0].action=='deliver':
                if any(i not in stock for i in items):return None
                t=max([t]+[stock[i][1] for i in items])
                # Esperar no armazém até à partida útil, reduzindo espera no cliente.
                t=max(t,batches[0].start-pd.Timedelta(minutes=p.handling+p.travel(loc,batches[0].location)[1]))
                if any((t-stock[i][0]).total_seconds()/60>p.dwell+1e-9 for i in items):return None
                stops.append(Stop(loc,'load',items,t));t+=pd.Timedelta(minutes=p.handling)
            for b in batches:
                t+=pd.Timedelta(minutes=p.travel(loc,b.location)[1]);t=max(t,b.start)
                if b.action=='pickup':t=max([t]+[p.requests[i].ordered_at for i in b.items])
                if t>b.end:return None
                stops.append(Stop(b.location,b.action,b.items,t));t+=pd.Timedelta(minutes=p.service);loc=b.location
            t+=pd.Timedelta(minutes=p.travel(loc,self.depot)[1])
            if batches[0].action=='pickup':
                arrival=t;stops.append(Stop(self.depot,'unload',items));t+=pd.Timedelta(minutes=p.handling)
                for i in items:stock[i]=(arrival,t)
            else:
                stops.append(Stop(self.depot,'visit'))
            if t>p.end:return None
            routes[v].stops.extend(stops);times[v]=t
        return tuple(routes),tuple(times),stock

    def decode(self,choices):
        state=self.initial()
        for d,o in enumerate(choices):
            state=self.extend(state,d,o)
            if state is None:return None
        if len(choices)==len(self.waves) and not self.problem.validate(state[0]).feasible:return None
        return state

    def heuristic(self,depth,kind):
        if kind not in ('h1','h2'):raise ValueError('Escolher h1 ou h2')
        return sum(b[0 if kind=='h1' else 1] for b in self.bounds[depth:])
