'use client';

import { useRouter } from 'next/navigation';
import SubmitForm from '@/components/SubmitForm';

export default function Home() {
  const router = useRouter();

  const handleJobCreated = (jobId: string) => {
    router.push(`/sets/${jobId}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-brick-light to-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-carbon mb-3">Tracklistify</h1>
          <p className="text-xl text-carbon/70">
            Turn DJ sets into tracklists using audio fingerprinting
          </p>
        </div>

        <SubmitForm onJobCreated={handleJobCreated} />
      </div>
    </div>
  );
}
