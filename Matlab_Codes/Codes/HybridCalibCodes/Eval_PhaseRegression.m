function Z = Eval_PhaseRegression(coef, phase)

% Z = 0;
% Reg = 1;
% for i=size(coef,3):-1:1
%     Z = Z + coef(:,:,i).*Reg;
%     Reg = Reg.*phase;
% 
% end


if(size(coef,3)<7)

    coef = cat(3, repmat(coef(:,:,1)*0,[1 1 7-size(coef,3)]), coef);

end


Z = coef(:,:,1).*phase.*phase.*phase.*phase.*phase.*phase + ...
    coef(:,:,2).*phase.*phase.*phase.*phase.*phase + ...
    coef(:,:,3).*phase.*phase.*phase.*phase + ...
    coef(:,:,4).*phase.*phase.*phase+ ...
    coef(:,:,5).*phase.*phase+ ...
    coef(:,:,6).*phase + ...
    coef(:,:,7);


end