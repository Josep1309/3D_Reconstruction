function [PCs, NewMask] = XYZtoPC(X,Y,Z,C,mask)

NewMask = mask;

for i = 1:size(X,3)

    M =[];
    Indi = mask(:,:,i)>0;
    Xd = X(:,:,i);
    Yd = Y(:,:,i);
    Zd = Z(:,:,i);
    M(:,1)=Xd(Indi); M(:,2)=Yd(Indi); M(:,3)=Zd(Indi);
    nubep=pointCloud(M);
    op = C(:,:,i);
    nubep.Color = uint8(repmat(op(Indi>0),[1 3]));

    [nubep,inlierIndex,outliers] = pcdenoise(nubep);
    
    index = find(Indi>0);
    Indi(index(outliers)) = 0; 
   
    NewMask(:,:,i) = Indi;

    if(size(X,3)>1)
        PCs{i} = nubep;
    else
        PCs = nubep;
    end
end


end