function Z = Eval_PhaseFrac(coef, phase)

% Z = 0;
% Reg = 1;
% for i=size(coef,3):-1:1
%     Z = Z + coef(:,:,i).*Reg;
%     Reg = Reg.*phase;
% 
% end


% if(size(coef,3)<6)
% 
%     coef = cat(3, repmat(coef(:,:,1)*0,[1 1 6-size(coef,3)]), coef);
% 
% end

if(size(coef,3)<5)
    coef(:,:,5) = 0;
end

Z = (coef(:,:,1) + coef(:,:,2).*phase + coef(:,:,5).*phase.*phase)./(1 + coef(:,:,3).*phase+ coef(:,:,4).*phase.*phase);




end