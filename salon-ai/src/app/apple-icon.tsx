import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
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
        <span
          style={{
            fontSize: 76,
            fontWeight: 700,
            color: "#22d3ee",
            fontFamily: "sans-serif",
            letterSpacing: -2,
          }}
        >
          SA
        </span>
      </div>
    ),
    { ...size }
  );
}
