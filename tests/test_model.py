import unittest
from pathlib import Path
from dataclasses import replace
import pandas as pd
from src.model import Problem, Stop, Route, example_route
from src.analysis import audit

ROOT=Path(__file__).resolve().parents[1]
class ModelTests(unittest.TestCase):
    def setUp(self):
        self.p=Problem(ROOT/'data_tiny')
        self.i=1
        self.r=self.p.requests[self.i]
        self.route=example_route(self.p,self.i)
    def check_bad(self,route,word):
        result=self.p.validate([route],require_all=False)
        self.assertFalse(result.feasible)
        self.assertTrue(any(word in s for s in result.errors),result.errors)
    def test_valid_partial(self):
        self.assertTrue(self.p.validate([self.route],False).feasible)
    def test_cost(self):
        expected=sum(self.p.travel(a,b)[0] for a,b in zip(
            [4,self.r.pickup,4,4,self.r.delivery],
            [self.r.pickup,4,4,self.r.delivery,4]))
        self.assertAlmostEqual(self.p.cost([self.route]),expected)
    def test_full_requires_all(self):
        self.assertFalse(self.p.validate([self.route]).feasible)
    def test_empty_full_invalid(self):
        self.assertFalse(self.p.validate([]).feasible)
    def test_skip_warehouse(self):
        self.route.stops=[self.route.stops[j] for j in (0,3,4)]
        self.check_bad(self.route,'incompleta')
    def test_vehicle_capacity(self):
        self.p.vehicles[1]=replace(self.p.vehicles[1],capacity=.1)
        self.check_bad(self.route,'capacidade')
    def test_warehouse_capacity(self):
        self.p.warehouses[4]=.1
        self.check_bad(self.route,'capacidade')
    def test_late(self):
        self.route.stops[0]=replace(self.route.stops[0],not_before=self.r.available_end+pd.Timedelta(minutes=1))
        self.check_bad(self.route,'janela')
    def test_wrong_location(self):
        self.route.stops[0]=replace(self.route.stops[0],location=4)
        self.check_bad(self.route,'local errado')
    def test_duplicate(self):
        self.route.stops.insert(1,self.route.stops[0])
        self.check_bad(self.route,'duplicada')
    def test_no_return(self):
        self.route.stops.pop()
        self.check_bad(self.route,'regressar')
    def test_unknown_item(self):
        self.route.stops[0]=replace(self.route.stops[0],items=(999,))
        self.check_bad(self.route,'desconhecido')
    def test_service_start_boundary(self):
        result=self.p.validate([self.route],False)
        start=result.timeline.iloc[0]['start']
        self.p.requests[1]=replace(self.r,available_end=start)
        self.assertTrue(self.p.validate([self.route],False).feasible)
    def test_transfer_between_vehicles(self):
        timeline=self.p.validate([self.route],False).timeline
        ready=timeline.iloc[1]['finish']
        route1=Route(1,self.route.start,self.route.stops[:2])
        route2=Route(2,ready,self.route.stops[2:])
        self.assertTrue(self.p.validate([route1,route2],False).feasible)
        route2.start=ready-pd.Timedelta(minutes=1)
        self.assertFalse(self.p.validate([route1,route2],False).feasible)
    def test_dwell(self):
        self.p.end+=pd.Timedelta(days=3)
        self.p.requests[1]=replace(self.r,delivery_end=self.p.end)
        t=self.p.validate([self.route],False).timeline.iloc[1]['arrival']
        self.route.stops[2]=replace(self.route.stops[2],not_before=t+pd.Timedelta(hours=25))
        self.check_bad(self.route,'permanência')
    def test_both_datasets(self):
        for folder,n in [('data_tiny',40),('data_small',80)]:
            p=Problem(ROOT/folder)
            self.assertEqual(len(p.requests),n)
            self.assertEqual(audit(p).problemas.sum(),0)
if __name__=='__main__': unittest.main()
