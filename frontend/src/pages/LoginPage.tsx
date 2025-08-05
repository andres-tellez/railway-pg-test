// src/pages/loginpage.tsx

import React, { useEffect } from "react";

const LoginPage = () => {
  useEffect(() => {
    // Automatically redirect to Flask backend to start Strava auth
    window.location.href = "http://localhost:5000/auth/login";
  }, []);

  return (
    <div className="text-center mt-20">
      <h1 className="text-2xl font-bold">Redirecting to Strava login...</h1>
    </div>
  );
};

export default LoginPage;
