"""Modelo preliminar: dados, custo em km e verificação de planos explícitos.
Não procura nem otimiza rotas. Ver README/notebook para as hipóteses.
"""
from dataclasses import dataclass, field
from pathlib import Path
import math
import pandas as pd

@dataclass(frozen=True)
class Request:
    id: int
    order_id: int
    pickup: int
    delivery: int
    weight: float
    available_start: pd.Timestamp
    available_end: pd.Timestamp
    delivery_start: pd.Timestamp
    delivery_end: pd.Timestamp
    ordered_at: pd.Timestamp

@dataclass(frozen=True)
class Vehicle:
    id: int
    depot: int
    capacity: float
    refrigerated: bool

@dataclass
class State:
    """Estado de um veículo durante a simulação de uma rota."""
    location: int
    time: pd.Timestamp
    onboard: set = field(default_factory=set)
    distance_km: float = 0.0

@dataclass(frozen=True)
class Stop:
    location: int
    action: str  # pickup, unload, load, deliver ou visit
    items: tuple = ()
    not_before: object = None  # instante mínimo para iniciar o serviço

@dataclass
class Route:
    vehicle_id: int
    start: object
    stops: list

@dataclass
class ValidationResult:
    feasible: bool
    cost_km: float
    errors: list
    timeline: pd.DataFrame

class Problem:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.tables = {p.stem: pd.read_csv(p) for p in self.folder.glob('*.csv')}
        required = {'rules','locations','distance_matrix','vehicles','products',
                    'orders','order_items','collection_centers','customers',
                    'localities','producers','delivery_locations'}
        missing = required - self.tables.keys()
        if missing:
            raise ValueError(f'Faltam tabelas: {sorted(missing)}')
        self.rules = dict(zip(self.tables['rules'].rule, self.tables['rules'].value))
        if self.rules['flow'] != 'producer>warehouse>delivery_location':
            raise ValueError('Fluxo não suportado')
        if self.rules['window_semantics'] != 'service_start':
            raise ValueError('Semântica de janelas não suportada')
        self.start = pd.Timestamp(self.rules['start_date'])
        self.end = self.start + pd.Timedelta(days=int(self.rules['horizon_days']))
        self.service = float(self.rules['stop_service_min'])
        self.handling = float(self.rules['warehouse_handling_min'])
        self.dwell = float(self.rules['max_warehouse_dwell_h']) * 60
        loc = self.tables['locations']
        self.locations = set(loc.location_id.astype(int))
        self.lookup = {(r.location_type, int(r.ref_id)): int(r.location_id)
                       for r in loc.itertuples()}
        self.warehouses = {self.lookup[('collection_center', int(r.center_id))]:
                           float(r.capacity_kg)
                           for r in self.tables['collection_centers'].itertuples()}
        self.vehicles = {int(r.vehicle_id): Vehicle(int(r.vehicle_id),
                         self.lookup[('collection_center', int(r.center_id))],
                         float(r.capacity_kg), bool(r.refrigerated))
                         for r in self.tables['vehicles'].itertuples()}
        self.distances = {(int(r.origin_location_id), int(r.destination_location_id)):
                          (float(r.distance_km), float(r.duration_min))
                          for r in self.tables['distance_matrix'].itertuples()}
        for x in self.locations:
            self.distances[x, x] = (0.0, 0.0)
        products = self.tables['products'].set_index('product_id')
        orders = self.tables['orders'].set_index('order_id')
        self.requests = {}
        for r in self.tables['order_items'].itertuples():
            o = orders.loc[r.order_id]
            self.requests[int(r.order_item_id)] = Request(
                int(r.order_item_id), int(r.order_id),
                self.lookup[('producer', int(products.loc[r.product_id,'producer_id']))],
                self.lookup[('delivery_location', int(o.delivery_location_id))],
                float(r.weight_kg), pd.Timestamp(r.availability_start),
                pd.Timestamp(r.availability_end), pd.Timestamp(r.delivery_start),
                pd.Timestamp(r.delivery_end), pd.Timestamp(o.order_datetime))

    def travel(self, origin, destination):
        return self.distances[origin, destination]

    def cost(self, routes):
        """Soma km das arestas indicadas; não acrescenta regresso implicitamente."""
        total = 0.0
        for route in routes:
            previous = self.vehicles[route.vehicle_id].depot
            for stop in route.stops:
                total += self.travel(previous, stop.location)[0]
                previous = stop.location
        return total

    def validate(self, routes, require_all=True):
        """Simula um plano completo ou um exemplo parcial.

        Uma Route por veículo, com várias viagens e esperas se necessário.
        Transferências entre veículos são permitidas no mesmo armazém.
        Erros são devolvidos em vez de aceitar uma solução inválida.
        """
        errors, log, phases = [], [], {}
        inventory_events = []
        used_vehicles = set()
        total = 0.0
        for route in routes:
            if route.vehicle_id not in self.vehicles:
                errors.append('Veículo desconhecido'); continue
            if route.vehicle_id in used_vehicles:
                errors.append('Usar uma única Route por veículo'); continue
            used_vehicles.add(route.vehicle_id)
            v = self.vehicles[route.vehicle_id]
            try:
                start = pd.Timestamp(route.start)
                if pd.isna(start): raise ValueError()
            except (ValueError, TypeError):
                errors.append('Data inicial inválida'); continue
            if not self.start <= start < self.end:
                errors.append('Início fora do horizonte')
            state = State(v.depot, start)
            for index, stop in enumerate(route.stops):
                tag = f'Veículo {v.id}, paragem {index+1}'
                if stop.location not in self.locations:
                    errors.append(f'{tag}: local desconhecido'); continue
                if stop.action not in {'pickup','unload','load','deliver','visit'}:
                    errors.append(f'{tag}: ação desconhecida'); continue
                if len(set(stop.items)) != len(stop.items):
                    errors.append(f'{tag}: itens repetidos'); continue
                if any(i not in self.requests for i in stop.items):
                    errors.append(f'{tag}: item desconhecido'); continue
                if (stop.action == 'visit' and stop.items) or (stop.action != 'visit' and not stop.items):
                    errors.append(f'{tag}: lista de itens incompatível com a ação'); continue
                try:
                    km, minutes = self.travel(state.location, stop.location)
                except KeyError:
                    errors.append(f'{tag}: ligação em falta'); continue
                if not all(math.isfinite(x) and x >= 0 for x in (km, minutes)):
                    errors.append(f'{tag}: distância/tempo inválidos'); continue
                arrival = state.time + pd.Timedelta(minutes=minutes)
                begin = arrival
                if stop.not_before is not None:
                    try:
                        nb = pd.Timestamp(stop.not_before)
                        if pd.isna(nb): raise ValueError()
                        begin = max(begin, nb)
                    except (ValueError, TypeError):
                        errors.append(f'{tag}: espera inválida'); continue
                reqs = [self.requests[i] for i in stop.items]
                if stop.action in {'pickup','deliver'}:
                    starts = [r.available_start if stop.action == 'pickup' else r.delivery_start for r in reqs]
                    begin = max([begin] + starts)
                    for r in reqs:
                        expected = r.pickup if stop.action == 'pickup' else r.delivery
                        deadline = r.available_end if stop.action == 'pickup' else r.delivery_end
                        if stop.location != expected:
                            errors.append(f'{tag}: local errado para item {r.id}')
                        if begin > deadline:
                            errors.append(f'{tag}: janela excedida para item {r.id}')
                        if stop.action == 'pickup' and begin < r.ordered_at:
                            errors.append(f'{tag}: recolha anterior à encomenda {r.order_id}')
                if stop.action in {'load','unload'} and stop.location not in self.warehouses:
                    errors.append(f'{tag}: operação fora do armazém')
                duration = (self.handling if stop.action in {'load','unload'} else
                            self.service if stop.action in {'pickup','deliver'} else 0)
                finish = begin + pd.Timedelta(minutes=duration)
                for r in reqs:
                    key = (r.id, stop.action)
                    if key in phases:
                        errors.append(f'{tag}: operação duplicada para item {r.id}')
                    else:
                        phases[key] = (begin, finish, arrival, stop.location, v.id)
                    if stop.action in {'pickup','load'}:
                        if r.id in state.onboard:
                            errors.append(f'{tag}: item {r.id} já a bordo')
                        state.onboard.add(r.id)
                    elif stop.action in {'unload','deliver'}:
                        if r.id not in state.onboard:
                            errors.append(f'{tag}: item {r.id} não está a bordo')
                        state.onboard.discard(r.id)
                    if stop.action == 'unload':
                        inventory_events.append((finish, 0, stop.location, r.weight))
                    elif stop.action == 'load':
                        inventory_events.append((begin, 1, stop.location, -r.weight))
                weight = sum(self.requests[i].weight for i in state.onboard)
                if weight > v.capacity + 1e-9:
                    errors.append(f'{tag}: capacidade do veículo excedida')
                if finish > self.end:
                    errors.append(f'{tag}: fim fora do horizonte')
                state.location, state.time = stop.location, finish
                state.distance_km += km
                log.append(dict(vehicle=v.id, stop=index+1, location=stop.location,
                                action=stop.action, items=str(stop.items), arrival=arrival,
                                start=begin, finish=finish, wait_min=(begin-arrival).total_seconds()/60,
                                load_kg=weight, distance_km=state.distance_km))
            if state.onboard:
                errors.append(f'Veículo {v.id}: termina com carga')
            if state.location != v.depot:
                errors.append(f'Veículo {v.id}: falta regressar ao armazém de origem')
            total += state.distance_km
        touched = {i for i, action in phases}
        expected = set(self.requests) if require_all else touched
        for i in expected:
            seq = [phases.get((i, a)) for a in ('pickup','unload','load','deliver')]
            if any(x is None for x in seq):
                errors.append(f'Item {i}: sequência produtor-armazém-cliente incompleta'); continue
            pickup, unload, load, deliver = seq
            if any(a[1] > b[0] for a,b in zip(seq, seq[1:])):
                errors.append(f'Item {i}: precedência temporal inválida')
            if pickup[4] != unload[4] or load[4] != deliver[4]:
                errors.append(f'Item {i}: mudança de veículo fora do armazém')
            if unload[3] != load[3]:
                errors.append(f'Item {i}: armazéns diferentes')
            if (load[0]-unload[2]).total_seconds()/60 > self.dwell + 1e-9:
                errors.append(f'Item {i}: permanência no armazém superior a 24 h')
        stock = {w: 0.0 for w in self.warehouses}
        for time, priority, location, delta in sorted(inventory_events):
            if location in stock:
                stock[location] += delta
                if stock[location] < -1e-9 or stock[location] > self.warehouses[location]+1e-9:
                    errors.append(f'Armazém {location}: inventário/capacidade inválidos em {time}')
        return ValidationResult(not errors, total, errors, pd.DataFrame(log))


def example_route(problem, item_id, vehicle_id=1):
    """Rota didática de UM item; não é solução para todas as encomendas."""
    r, v = problem.requests[item_id], problem.vehicles[vehicle_id]
    start = max(problem.start, r.ordered_at,
                r.available_start-pd.Timedelta(minutes=problem.travel(v.depot,r.pickup)[1]))
    return Route(vehicle_id, start, [Stop(r.pickup,'pickup',(item_id,)),
        Stop(v.depot,'unload',(item_id,)), Stop(v.depot,'load',(item_id,)),
        Stop(r.delivery,'deliver',(item_id,)), Stop(v.depot,'visit')])
