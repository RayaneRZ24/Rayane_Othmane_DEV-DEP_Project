"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { MetricPoint } from "@/lib/replay";
echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer]);

export function MetricChart({ points, label, cursor, detections }: { points: MetricPoint[]; label: string; cursor: number | null; detections: number[] }) {
  const element = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.EChartsType | null>(null);
  useEffect(() => {
    if (!element.current) return;
    chart.current = echarts.init(element.current);
    const observer = new ResizeObserver(() => chart.current?.resize());
    observer.observe(element.current);
    return () => { observer.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);
  useEffect(() => {
    chart.current?.setOption({
      animation: false, grid: { left: 50, right: 25, top: 25, bottom: 45 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "value", name: "Observation", nameLocation: "middle", nameGap: 30, nameTextStyle: { color: "#91a1b7" }, minInterval: 1,
        splitNumber: 4, min: points[0]?.sample_index ?? 0, max: Math.max(cursor ?? 1, 1),
        axisLabel: { color: "#8799b4", fontSize: 10, hideOverlap: true },
        axisLine: { lineStyle: { color: "#2b3749" } }, splitLine: { show: false } },
      yAxis: { type: "value", min: 0, max: 1, axisLabel: { color: "#8799b4", fontSize: 10 },
        splitLine: { lineStyle: { color: "#253042" } } },
      dataZoom: [{ type: "inside" }],
      series: [{ name: label, type: "line", showSymbol: points.length === 1, connectNulls: false,
        lineStyle: { color: "#92b6ff", width: 2 }, itemStyle: { color: "#92b6ff" },
        markLine: { symbol: "none", label: { show: false }, lineStyle: { color: "#dfae6a", type: "dashed" }, data: detections.filter(i => i >= (points[0]?.sample_index ?? 0) && i <= (cursor ?? -1)).map(i => ({ xAxis: i })) },
        areaStyle: { color: "#92b6ff", opacity: .05 }, data: points.map(p => [p.sample_index, p.value]) }],
    }, true);
  }, [points, label, cursor, detections]);
  return <div className="chart-wrap"><div className="chart" ref={element} role="img" aria-label={`Évolution de ${label}`} />{!points.length && <span className="chart-empty">Lancez la lecture pour consulter les observations.</span>}</div>;
}
