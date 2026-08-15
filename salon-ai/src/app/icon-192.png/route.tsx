import { ImageResponse } from "next/og";

export const size = { width: 192, height: 192 };
export const contentType = "image/png";

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0b0f18 0%, #05070d 100%)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 132,
            height: 132,
            borderRadius: 28,
            background: "rgba(34, 211, 238, 0.14)",
            border: "3px solid rgba(34, 211, 238, 0.35)",
          }}
        >
          <span
            style={{
              fontSize: 64,
              fontWeight: 700,
              color: "#22d3ee",
              fontFamily: "sans-serif",
              letterSpacing: -2,
            }}
          >
            SA
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}
