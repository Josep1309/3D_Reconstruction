function [ph, mask, texture,gm] = ComputeNStepPhase(I, gammaTh, NStep)

I1 = I(:, :, 1);

S = zeros(size(I1));
C = zeros(size(I1));
Ip = zeros(size(I1));


L = NStep; fs = NStep;
T = 1/fs;
t = (0:L-1)*T;
senial = 255*cos(t*2*pi).*fftshift(hanning(L)');
Y = fft(I,[],3).*reshape(fft(senial),[1 1 numel(senial)]);
I = ifft(Y,[],3);


for i = 1: NStep
    I1 = I(:, :, i);
    S = S + I1 * sin(2*pi/(NStep) * (i-1));
    C = C + I1 * cos(2*pi/(NStep) * (i-1));
    Ip= Ip + I1/NStep;
end

Idp = 2 * sqrt(C.^2 + S.^2)/NStep;
ph = -atan2(S, C);
mask = ones(size(I1))*255;
gm = Idp./Ip;

mask (gm < gammaTh) = 0;

texture = uint8(Idp + Ip);

end