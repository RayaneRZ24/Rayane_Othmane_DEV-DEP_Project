"use client";

import { useEffect, useRef } from "react";
import { init, use, type EChartsType } from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

export type LatencyPoint = { time: number; latency: number };

export function LatencyChart({ points }: { points: LatencyPoint[] }) {
  const element = useRef<HTMLDivElement>(null);
  const chart = useRef<EChartsType | null>(null);

  useEffect(() => {
    if (!element.current) return;
    chart.current = init(element.current, undefined, { renderer: "canvas" });
    const observer = new ResizeObserver(() => chart.current?.resize());
    observer.observe(element.current);
    return () => { observer.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    chart.current?.setOption({
      animation: false,
      grid: { top: 18, left: 48, right: 16, bottom: 34 },
      tooltip: { trigger: "axis", backgroundColor: "#161c28", borderColor: "#30394a", textStyle: { color: "#ecf0f6" } },
      xAxis: {
        type: "time", axisLine: { lineStyle: { color: "#28313f" } },
        axisLabel: { color: "#8390a4", hideOverlap: true }, splitLine: { show: false },
      },
      yAxis: {
        type: "value", name: "ms", min: 0, nameTextStyle: { color: "#8390a4" },
        axisLabel: { color: "#8390a4" }, splitLine: { lineStyle: { color: "#222b37", type: "dashed" } },
      },
      series: [{
        name: "Temps de réponse (ms)", type: "line", smooth: false, showSymbol: points.length < 2,
        symbolSize: 6, lineStyle: { color: "#7daaff", width: 2 }, itemStyle: { color: "#7daaff" },
        areaStyle: { color: "rgba(104,155,255,0.07)" },
        data: points.map((point) => [point.time, point.latency]),
      }],
    });
  }, [points]);

  return <div className="chart-wrap" role="img" aria-label="Évolution du temps de réponse du service en millisecondes">
    <div ref={element} className="chart" />
    {points.length === 0 && <p className="chart-empty">En attente des premières mesures…</p>}
  </div>;
}
