import React from 'react';

interface StravaConnectButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

const StravaConnectButton: React.FC<StravaConnectButtonProps> = ({ onClick, disabled = false }) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center justify-center bg-[#FC5200] hover:bg-[#E64700] disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-md hover:shadow-lg disabled:cursor-not-allowed"
      style={{ height: '48px', minWidth: '200px' }}
    >
      {/* Official Strava Connect Button */}
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="mr-2">
        <path
          d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.599h4.172L10.463 0l-7.02 13.828h4.169"
          fill="currentColor"
        />
      </svg>
      Connect with Strava
    </button>
  );
};

export default StravaConnectButton;
