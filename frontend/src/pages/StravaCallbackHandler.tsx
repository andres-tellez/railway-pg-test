// frontend/src/pages/StravaCallbackHandler.tsx
import React, { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";

const StravaCallbackHandler: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const code = searchParams.get("code");
    const userId = searchParams.get("state"); // ← comes from JWT `sub`

    if (!code || !userId) {
      console.error("Missing code or user_id");
      navigate("/error");
      return;
    }

    // 🔁 Exchange Strava code for tokens on backend
    axios
      .post(`${import.meta.env.VITE_API_BASE_URL}/auth/callback`, {
        code,
        user_id: userId,
      })
      .then((res) => {
        console.log("✅ Strava callback success", res.data);
        navigate("/dashboard?strava=success");
      })
      .catch((err) => {
        console.error("❌ Strava callback error", err);
        navigate("/error");
      });
  }, [searchParams, navigate]);

  return <div>Linking your Strava account...</div>;
};

export default StravaCallbackHandler;
