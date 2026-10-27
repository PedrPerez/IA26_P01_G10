"""Greedy best-first (f=h) e A* (f=g+h), com limite explícito."""
from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count
from time import perf_counter

@dataclass
class SearchResult:
    algorithm: str
    routes: object
    choices: tuple
    cost_km: float
    expanded: int
    generated: int
    seconds: float
    status: str

def search(planner,algorithm='astar',heuristic='h2',max_expanded=20000):
    if algorithm not in ('astar','greedy'):raise ValueError('Algoritmo desconhecido')
    start=perf_counter();counter=count();heap=[];expanded=0;generated=1
    heappush(heap,(planner.heuristic(0,heuristic),0,next(counter),0.,(),planner.initial()))
    while heap and expanded<max_expanded:
        _,_,_,g,choices,state=heappop(heap);depth=len(choices)
        if depth==len(planner.waves):
            if planner.problem.validate(state[0]).feasible:
                return SearchResult(algorithm+' '+heuristic,state[0],choices,g,expanded,generated,perf_counter()-start,'solução')
            continue
        expanded+=1
        for option in planner.options[depth]:
            child=planner.extend(state,depth,option)
            if child is None:continue
            cost=g+planner.option_cost(planner.waves[depth],option)
            h=planner.heuristic(depth+1,heuristic)
            score=h if algorithm=='greedy' else cost+h
            heappush(heap,(score,-(depth+1),next(counter),cost,choices+(option,),child));generated+=1
    status='limite de nós' if heap else 'sem solução neste espaço'
    return SearchResult(algorithm+' '+heuristic,None,(),float('inf'),expanded,generated,perf_counter()-start,status)
