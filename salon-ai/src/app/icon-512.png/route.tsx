import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
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
            width: 352,
            height: 352,
            borderRadius: 76,
            background: "rgba(34, 211, 238, 0.14)",
            border: "8px solid rgba(34, 211, 238, 0.35)",
          }}
        >
          <span
            style={{
              fontSize: 170,
              fontWeight: 700,
              color: "#22d3ee",
              fontFamily: "sans-serif",
              letterSpacing: -6,
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
