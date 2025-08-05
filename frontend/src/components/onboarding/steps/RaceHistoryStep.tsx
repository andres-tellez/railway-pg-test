import { useFormContext } from 'react-hook-form';
import { OnboardingFormData } from '../../../schemas/onboardingSchema';

const pastRaceOptions = ['5K', '10K', 'Half Marathon', 'Marathon', 'Ultra', "Haven't raced yet"] as const;

export default function RaceHistoryStep() {
  const { register, watch, setValue, getValues } = useFormContext<OnboardingFormData>();
  const raceHistory = watch('raceHistory');

  // Helper to handle checkbox array for pastRaces
  const handlePastRaceChange = (race: typeof pastRaceOptions[number]) => {
    const current = getValues('pastRaces') as readonly typeof pastRaceOptions[number][] || [];
    if (current.includes(race)) {
      setValue('pastRaces', current.filter((r) => r !== race));
    } else {
      setValue('pastRaces', [...current, race]);
    }
  };

  const pastRaces = watch('pastRaces') || [];

  return (
    <div className="space-y-6">
      <div>
        <label className="block font-semibold">Have you raced before?</label>
        <div className="flex gap-4 mt-2">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              value="true"
              onChange={() => setValue('raceHistory', true)}
              checked={raceHistory === true}
            />
            Yes
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              value="false"
              onChange={() => setValue('raceHistory', false)}
              checked={raceHistory === false}
            />
            No
          </label>
        </div>
      </div>

      {raceHistory === true && (
        <div>
          <label className="block font-semibold mt-4">Which distances have you raced?</label>
          <div className="flex flex-wrap gap-4 mt-2">
            {pastRaceOptions.map((race) => (
              <label key={race} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  value={race}
                  checked={pastRaces.includes(race)}
                  onChange={() => handlePastRaceChange(race)}
                />
                {race}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
