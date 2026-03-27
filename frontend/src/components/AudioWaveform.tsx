import { useRef, useEffect } from 'react';

interface Props {
  stream: MediaStream | null;
  width?: number;
  height?: number;
}

export default function AudioWaveform({ stream, width, height = 80 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // If no stream, draw a flat line and bail out
    if (!stream) {
      drawIdle(ctx, canvas.width, canvas.height);
      return;
    }

    const audioCtx = new AudioContext();
    audioCtxRef.current = audioCtx;

    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.8;

    const source = audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      // Create gradient from indigo to cyan
      const gradient = ctx.createLinearGradient(0, 0, w, 0);
      gradient.addColorStop(0, '#4f46e5');
      gradient.addColorStop(1, '#06b6d4');

      const barCount = bufferLength;
      const gap = 2;
      const barWidth = (w - gap * (barCount - 1)) / barCount;

      for (let i = 0; i < barCount; i++) {
        const value = dataArray[i] / 255;
        const barHeight = Math.max(value * h, 2); // minimum 2px so bars are always visible

        const x = i * (barWidth + gap);
        const y = (h - barHeight) / 2; // center vertically

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();
      }
    };

    draw();

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      source.disconnect();
      audioCtx.close();
      audioCtxRef.current = null;
    };
  }, [stream]);

  // Resize canvas to match container / props
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        canvas.width = w;
        canvas.height = h;
      }
    });

    if (width) {
      canvas.width = width;
    }
    canvas.height = height;

    resizeObserver.observe(canvas);
    return () => resizeObserver.disconnect();
  }, [width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: width ? `${width}px` : '100%',
        height: `${height}px`,
        display: 'block',
      }}
    />
  );
}

/** Draw a centered flat line for the idle / no-stream state */
function drawIdle(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.clearRect(0, 0, w, h);

  const gradient = ctx.createLinearGradient(0, 0, w, 0);
  gradient.addColorStop(0, '#4f46e5');
  gradient.addColorStop(1, '#06b6d4');

  ctx.strokeStyle = gradient;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();
}
