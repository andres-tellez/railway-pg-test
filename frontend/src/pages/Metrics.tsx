import React from 'react';
import { useSearchParams } from 'react-router-dom';
import MetricsLayout from '../components/layout/MetricsLayout';
import SimpleMetrics from './SimpleMetrics';
import GYRMetricsDemo from './GYRMetricsDemo';

const Metrics: React.FC = () => {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview';

  const renderTabContent = () => {
    switch (activeTab) {
      case 'gyr':
        return <GYRMetricsDemo />;
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
