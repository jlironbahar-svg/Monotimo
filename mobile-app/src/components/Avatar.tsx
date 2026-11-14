
import type { Mood } from '../../../shared/protocol';
import { CustomAvatar } from './CustomAvatar';
import { Puppy } from './Puppy';

interface Props {
  uri: string | null;
  size?: number;
  mood?: Mood;
  talking?: boolean;
  onPress?: () => void;
}

export function Avatar({ uri, ...rest }: Props) {
  return uri ? <CustomAvatar uri={uri} {...rest} /> : <Puppy {...rest} />;
}
