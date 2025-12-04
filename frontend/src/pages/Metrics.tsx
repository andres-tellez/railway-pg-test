import React from 'react';
import { useSearchParams } from 'react-router-dom';
import MetricsLayout from '../components/layout/MetricsLayout';
import SimpleMetrics from './SimpleMetrics';

const Metrics: React.FC = () => {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview';

  const renderTabContent = () => {
    // GYR Scores tab has been hidden - only show Overview
    switch (activeTab) {
      case 'overview':
      default:
        return <SimpleMetrics />;
    }
  };

  return (
    <MetricsLayout>
      {renderTabContent()}
    </MetricsLayout>
  );
};

export default Metrics;
